import numpy as np
from qpoint_class import QPoint
import healpy as hp
import ctypes as ct

import _libqpoint as lib
from _libqpoint import libqp as qp

__all__ = ['QMap', 'check_map', 'check_proj']

def check_map(map_in, copy=False, partial=False, dtype=np.double):
    """
    Return a properly transposed and memory-aligned map and its nside.

    Arguments
    ---------
    map_in : map or list of maps
        Input map(s)
    copy : bool, optional
        If True, ensure that output map does not share memory with
        the input map.   Use if you do not want in-place operations to
        modify the map contents.
    partial : bool, optional
        If True, the map is not checked to ensure a proper healpix nside,
        and the number of pixels is returned instead.

    Returns
    -------
    map_out : numpy.ndarray
        Properly shaped and memory-aligned map, copied from the input
        if necessary.
    nside or npix : int
        If partial is False, the map nside. Otherwise, the number of pixels.
    """
    map_out = np.atleast_2d(map_in)
    if np.argmax(map_out.shape) == 0:
        map_out = map_out.T
    if partial:
        nside = len(map_out[0])
    else:
        nside = hp.get_nside(map_out)
    map_out = lib.check_input('map', map_out, dtype=dtype)
    if copy and np.may_share_memory(map_in, map_out):
        map_out = map_out.copy()
    return map_out, nside

def check_proj(proj_in, copy=False, partial=False):
    """
    Return a properly transposed and memory-aligned projection map,
    its nside, and the map dimension.

    Arguments
    ---------
    proj_in : map or list of maps
        Input projection matrix map
    copy : bool, optional
        If True, ensure that output map does not share memory with
        the input map.   Use if you do not want in-place operations to
        modify the map contents.
    partial : bool, optional
        If True, the map is not checked to ensure a proper healpix nside,
        and the number of pixels is returned instead.

    Returns
    -------
    map_out : numpy.ndarray
        Properly shaped and memory-aligned map, copied from the input
        if necessary.
    nside or npix : int
        If partial is False, the map nside. Otherwise, the number of pixels.
    nmap : int
        The map size this projection matrix is intended to invert, i.e.
        the solution to `len(proj) = nmap * (nmap + 1) / 2`.  Raises an
        error if an integer solution is not found.
    """
    proj_out, nside = check_map(proj_in, copy=copy, partial=partial)
    nmap = int(np.roots([1, 1, - 2 * len(proj_out)]).max())
    if (nmap * (nmap + 1) /2 != len(proj_out)):
        raise ValueError, 'proj has incompatible shape'
    return proj_out, nside, nmap

class QMap(QPoint):
    """
    Quaternion-based mapmaker that generates per-channel pointing
    on-the-fly.
    """

    def __init__(self, nside=256, pol=True,
                 source_map=None, source_pol=True,
                 q_bore=None, ctime=None, q_hwp=None, **kwargs):
        """
        Initialize the internal structures and data depo for
        mapmaking and/or timestream generation.

        Arguments
        ---------
        nside : int, optional
            Resolution of the output maps. Default: 256
        pol : bool, optional
            If True, output maps are polarized.
        source_map : array_like, optional
            If supplied, passed to `init_source()` to initialize
            the source map structure.
        source_pol : bool, optional
            If True, source_map is polarized.  See `init_source()`
            for details.
        q_bore, ctime, q_hwp : array_like, optional
            Boresight pointing data.  See `init_point()` for details.
            If not supplied, the pointing structure is left
            uninitialized.

        Remaining arguments are passed to `QPoint.set()`.

        Notes
        -----
        An internal `depo` dictionary attribute stores the source and output
        maps, timestreams, and pointing data for retrieval by the user.
        Only pointers to these arrays in memory are passed to the C
        library.  To ensure that extraneous copies of data are not made,
        supply these methods with C-contiguous arrays of the correct shape.
        """
        super(QMap, self).__init__(**kwargs)

        self.depo = dict()
        """
        Dictionary of source and output maps, timetreams and pointing data.
        Pointers to these arrays in memory are passed to the C library.
        """

        self.reset()

        self.init_dest(nside=nside, pol=pol)

        if source_map is not None:
            self.init_source(source_map, pol=source_pol)

        if q_bore is not None:
            self.init_point(q_bore, ctime=ctime, q_hwp=q_hwp)

    def source_is_init(self):
        """
        Return True if the source map is initialized, otherwise False.
        """
        if not hasattr(self, '_source'):
            return False
        if not self._source.contents.init:
            return False
        return True

    def init_source(self, source_map, pol=True, pixels=None, nside=None,
                    reset=False):
        """
        Initialize the source map structure.  Timestreams are
        produced by scanning this map.

        Arguments
        ---------
        source_map : array_like
            Input map.  Must be of shape (N, npix), where N can be
            1, 3, 6, 9, or 18.
        pol : bool, optional
            If True, and the map shape is (3, npix), then input is a
            polarized map (and not T + 1st derivatives).
        pixels : 1D array_like, optional
            Array of pixel numbers for each map index, if `source_map` is
            a partial map.
        nside : int, optional
            map dimension.  If `pixels` is supplied, this argument is required.
            Otherwise, the nside is determined from the input map.
        reset : bool, optional
            If True, and if the structure has already been initialized,
            it is reset and re-initialized with the new map.  If False,
            a RuntimeError is raised if the structure has already been
            initialized.

        Notes
        -----
        This method will automatically determine the type of map
        given its shape.  Note that for N=3, the pol keyword argument
        should be used to disambiguate the two map types.  By default,
        a polarized map with (T,Q,U) components is assumed.

        N     map_in contents
        1  :  T
        3  :  (T, Q, U) --or-- (T, dTdt, dTdp)
        6  :  (T, dTdt, dTdp) + (dT2dt2, dT2dpdt, dT2dp2)
        9  :  (T, Q, U) + (dTdt, dQdt, dUdt, dTdp, dQdp, dUdp)
        18 :  (N=9) + (dT2dt2, dQ2dt2, dU2dt2, dT2dpdt, dQ2dpdt, dU2dpdt,
                       dT2dp2, dQ2dp2, dU2dp2)
        """

        if self.source_is_init():
            if reset:
                self.reset_source()
            else:
                raise RuntimeError, 'source already initialized'

        if pixels is None:
            partial = False
        else:
            partial = True
            if nside is None:
                raise ValueError, 'nside required for partial maps'

        # check map shape and create pointer
        smap, snside = check_map(source_map, partial=partial)
        if not partial:
            nside = snside
            npix = hp.nside2npix(nside)
        else:
            npix = len(pixels)

        # store map
        self.depo['source_map'] = smap
        self.depo['source_nside'] = nside
        if partial:
            self.depo['source_pixels'] = pixels

        # initialize
        source = self._source.contents
        source.partial = partial
        source.nside = nside
        source.npix = npix
        source.pixinfo_init = 0
        source.pixinfo = None
        source.pixhash_init = 0
        source.pixhash = None
        source.num_vec = len(source_map)
        source.vec_mode = lib.get_vec_mode(smap, pol)
        source.vec1d = lib.as_ctypes(smap.ravel())
        source.vec1d_init = lib.QP_ARR_INIT_PTR
        source.vec = None
        source.vec_init = 0
        source.num_proj = 0
        source.proj_mode = 0
        source.proj = None
        source.proj_init = 0
        source.proj1d = None
        source.proj1d_init = 0
        source.init = lib.QP_STRUCT_INIT

        if partial:
            if qp.qp_init_map_pixhash(self._source, pixels, npix):
                raise RuntimeError, 'Error initializing source pixhash'

        if qp.qp_reshape_map(self._source):
            raise RuntimeError, 'Error reshaping source map'

    def reset_source(self):
        """
        Reset the source map structure.  Must be reinitialized to
        produce more timestreams.
        """
        if hasattr(self, '_source'):
            qp.qp_free_map(self._source)
        self.depo.pop('source_map', None)
        self.depo.pop('source_nside', None)
        self.depo.pop('source_pixels', None)
        self._source = ct.pointer(lib.qp_map_t())

    def source_is_pol(self):
        """
        Return True if the source map is polarized, otherwise False.
        Raise an error if source map is not initialized.
        """
        if not self.source_is_init():
            raise RuntimeError, 'source map not initialized'

        if self._source.contents.vec_mode in [2,4,6]:
            return True
        return False

    def dest_is_init(self):
        """
        Return True if the dest map is initialized, otherwise False.
        """
        if not hasattr(self, '_dest'):
            return False
        if not self._dest.contents.init:
            return False
        return True

    def init_dest(self, nside=None, pol=True, vec=None, proj=None, pixels=None,
                  copy=False, reset=False):
        """
        Initialize the destination map structure.  Timestreams are binned
        and projection matrices accumulated into this structure.

        Arguments
        ---------
        nside : int, optional
            map dimension.  If `pixels` is supplied, this argument is required.
            Otherwise, the default is 256.
        pol : bool, optional
            If True, a polarized map will be created.
        vec : array_like or bool, optional, shape (N, npix)
            If supplied, nside and pol are determined from this map, and
            the vector (binned signal) map is initialized from this.
            If False, accumulation of this map from timestreams is disabled.
        proj : array_like or bool, optional, shape (N*(N+1)/2, npix)
            Array of upper-triangular elements of the projection matrix
            for each pixel.  If not supplied, a blank map of the appropriate
            shape is created. If False, accumulation of the projection matrix
            is disabled.
        pixels : 1D array_like, optional
            Array of pixel numbers for each map index, if `vec` and `proj` are
            partial maps.
        copy : bool, optional
            If True and vec/proj are supplied, make copies of these inputs
            to avoid in-place operations.
        reset : bool, optional
            If True, and if the structure has already been initialized,
            it is reset and re-initialized with the new map.  If False,
            a RuntimeError is raised if the structure has already been
            initialized.
        """

        if vec is False and proj is False:
            raise ValueError('one of vec or proj must not be False')

        if self.dest_is_init():
            if reset:
                self.reset_dest()
            else:
                raise RuntimeError,'dest already initialized'

        if pixels is None:
            if nside is None:
                nside = 256
            npix = hp.nside2npix(nside)
            partial = False
        else:
            if nside is None:
                raise ValueError, 'nside required for partial maps'
            npix = len(pixels)
            partial = True

        if vec is None:
            if pol:
                vec = np.zeros((3, npix), dtype=np.double)
            else:
                vec = np.zeros((1, npix), dtype=np.double)
        elif vec is not False:
            vec, vnside = check_map(vec, copy=copy, partial=partial)
            if not partial:
                nside = vnside
                npix = hp.nside2npix(nside)
            if len(vec) == 1:
                pol = False
            elif len(vec) == 3:
                pol = True
            else:
                raise ValueError('vec has incompatible shape')

        if proj is None:
            if pol:
                proj = np.zeros((6, npix), dtype=np.double)
            else:
                proj = np.zeros((1, npix), dtype=np.double)
        elif proj is not False:
            proj, pnside, pnmap = check_proj(proj, copy=copy, partial=partial)

            if vec is not False:
                if pnmap != len(vec):
                    raise ValueError('proj has incompatible shape')
                if len(proj) != [1,6][pol]:
                    raise ValueError('proj has incompatible shape')
                if pnside != nside:
                    raise ValueError('proj has incompatible nside')
            else:
                if len(proj) == 1:
                    pol = False
                elif len(proj) == 6:
                    pol = True
                else:
                    raise ValueError('proj has incompatible shape')
                if not partial:
                    nside = pnside
                    npix = hp.nside2npix(nside)

        # store arrays for later retrieval
        self.depo['vec'] = vec
        self.depo['proj'] = proj
        self.depo['dest_nside'] = nside

        if partial:
            self.depo['dest_pixels'] = pixels

        # initialize
        ret = ()
        dest = self._dest.contents
        dest.nside = nside
        dest.npix = npix
        dest.partial = partial
        dest.pixinfo_init = 0
        dest.pixinfo = None
        dest.pixhash_init = 0
        dest.pixhash = None
        if vec is not False:
            dest.num_vec = len(vec)
            dest.vec_mode = lib.get_vec_mode(vec, pol)
            dest.vec1d = lib.as_ctypes(vec.ravel())
            dest.vec1d_init = lib.QP_ARR_INIT_PTR
            ret += (vec.squeeze(),)
        if proj is not False:
            dest.num_proj = len(proj)
            dest.proj_mode = lib.get_proj_mode(proj, pol)
            dest.proj1d = lib.as_ctypes(proj.ravel())
            dest.proj1d_init = lib.QP_ARR_INIT_PTR
            ret += (proj.squeeze(),)
        dest.vec = None
        dest.vec_init = 0
        dest.proj = None
        dest.proj_init = 0
        dest.init = lib.QP_STRUCT_INIT

        if partial:
            if qp.qp_init_map_pixhash(self._dest, pixels, npix):
                raise RuntimeError, 'Error initializing dest pixhash'

        if qp.qp_reshape_map(self._dest):
            raise RuntimeError, 'Error reshaping dest map'

        # return
        if len(ret) == 1:
            return ret[0]
        return ret

    def reset_dest(self):
        """
        Reset the destination map structure.
        Must be reinitialized to continue mapmaking.
        """
        if hasattr(self, '_dest'):
            qp.qp_free_map(self._dest)
        self.depo.pop('vec', None)
        self.depo.pop('proj', None)
        self.depo.pop('dest_nside', None)
        self.depo.pop('dest_pixels', None)
        self._dest = ct.pointer(lib.qp_map_t())

    def dest_is_pol(self):
        """
        Return True if the destination map is polarized, otherwise False.
        Raise an error if destination map is not initialized.
        """
        if not self.dest_is_init():
            raise RuntimeError, 'dest map not initialized'

        if 2 in [self._dest.contents.vec_mode, self._dest.contents.proj_mode]:
            return True
        return False

    def point_is_init(self):
        """
        Return True if the point map is initialized, otherwise False.
        """
        if not hasattr(self, '_point'):
            return False
        if not self._point.contents.init:
            return False
        return True

    def init_point(self, q_bore=None, ctime=None, q_hwp=None):
        """
        Initialize or update the boresight pointing data structure.

        Arguments
        ---------
        q_bore : array_like, optional
             Boresight pointing quaternion, of shape (nsamp, 4).
             If supplied, the pointing structure is reset if already
             initialized.
        ctime : array_like, optional
             time since the UTC epoch.  If not None, the time array
             is updated to this. Shape must be (nsamp,)
        q_hwp : array_like, optional
             Waveplate quaternion.  If not None, the quaternion is
             updated to this. Shape must be (nsamp, 4)
        """

        if not hasattr(self, '_point'):
            self.reset_point()

        point = self._point.contents

        if q_bore is not None:
            if point.init:
                self.reset_point()
            point = self._point.contents
            q_bore = lib.check_input('q_bore', q_bore)
            n = q_bore.size / 4
            point.n = n
            self.depo['q_bore'] = q_bore
            point.q_bore = lib.as_ctypes(q_bore)
            point.q_bore_init = lib.QP_ARR_INIT_PTR
            point.init = lib.QP_STRUCT_INIT

        if not point.init:
            raise RuntimeError, 'point not initialized'

        n = point.n

        if ctime is False:
            point.ctime_init = 0
            point.ctime = None
        elif ctime is not None:
            ctime = lib.check_input('ctime', ctime, shape=(n,))
            self.depo['ctime'] = ctime
            point.ctime_init = lib.QP_ARR_INIT_PTR
            point.ctime = lib.as_ctypes(ctime)

        if q_hwp is False:
            point.q_hwp_init = 0
            point.q_hwp = None
        elif q_hwp is not None:
            q_hwp = lib.check_input('q_hwp', q_hwp, shape=(n, 4))
            self.depo['q_hwp'] = q_hwp
            point.q_hwp_init = lib.QP_ARR_INIT_PTR
            point.q_hwp = lib.as_ctypes(q_hwp)

    def reset_point(self):
        """
        Reset the pointing data structure.
        """
        if hasattr(self, '_point'):
            qp.qp_free_point(self._point)
        self.depo.pop('q_bore', None)
        self.depo.pop('ctime', None)
        self.depo.pop('q_hwp', None)
        self._point = ct.pointer(lib.qp_point_t())

    def init_detarr(self, q_off, weight=None, gain=None, poleff=None, tod=None,
                    flag=None, do_diff=False, write=False):
        """
        Initialize the detector listing structure.  Detector properties and
        timestreams are passed to and from the mapmaker through this structure.

        Arguments
        ---------
        q_off : array_like
            Array of offset quaternions, of shape (ndet, 4).
        weight : array_like, optional
            Per-channel mapmaking weights, of shape (ndet,) or a constant.
            Default : 1.
        gain : array_like, optional
            Per-channel gains, of shape (ndet,) or a constant.
            Default : 1.
        poleff : array_like, optional
            Per-channel polarization efficiencies, of shape(ndet,) or a constant.
            Default: 1.
        tod : array_like, optional
            Timestream array, of shape (ndet, nsamp).  nsamp must match that of
            the pointing structure.  If not supplied and `write` is True, then
            a zero-filled timestream array is initialized.
        flag : array_like, optional
            Flag array, of shape (ndet, nsamp), for excluding data from
            mapmaking.  nsamp must match that of the pointing structure.
            If not supplied, a zero-filled array is initialized (i.e. no 
            flagged samples).
        write : bool, optional
             If True, the timestreams are ensured writable and created if
             necessary.
        """

        self.reset_detarr()

        # check inputs
        q_off = lib.check_input('q_off', np.atleast_2d(q_off))
        n = q_off.size / 4
        weight = lib.check_input('weight', weight, shape=(n,), fill=1)
        gain = lib.check_input('gain', gain, shape=(n,), fill=1)
        poleff = lib.check_input('poleff', poleff, shape=(n,), fill=1)

        ns = self._point.contents.n
        shape = (n, ns)

        if tod is not None:
            tod = np.atleast_2d(tod)

        if write:
            tod = lib.check_output('tod', tod, shape=shape, fill=0)
            self.depo['tod'] = tod
        elif tod is not None:
            tod = lib.check_input('tod', tod, shape=shape)
            self.depo['tod'] = tod
        if flag is not None:
            flag = lib.check_input('flag', np.atleast_2d(flag),
                                   dtype=np.uint8, shape=shape)
            self.depo['flag'] = flag

        # populate array
        dets = (lib.qp_det_t * n)()
        for idx, (q, w, g, p) in enumerate(zip(q_off, weight, gain, poleff)):
            dets[idx].init = lib.QP_STRUCT_INIT
            dets[idx].q_off = lib.as_ctypes(q)
            dets[idx].weight = w
            dets[idx].gain = g
            dets[idx].poleff = p
            if tod is not None:
                dets[idx].n = ns
                dets[idx].tod_init = lib.QP_ARR_INIT_PTR
                dets[idx].tod = lib.as_ctypes(tod[idx])
            else:
                dets[idx].tod_init = 0
            if flag is not None:
                dets[idx].n = ns
                dets[idx].flag_init = lib.QP_ARR_INIT_PTR
                dets[idx].flag = lib.as_ctypes(flag[idx])
            else:
                dets[idx].flag_init = 0

        detarr = lib.qp_detarr_t()
        detarr.n = n
        detarr.init = lib.QP_STRUCT_INIT
        detarr.arr_init = lib.QP_ARR_INIT_PTR
        detarr.arr = dets
        detarr.diff=0

        if do_diff:
            detarr.diff=1

        self._detarr = ct.pointer(detarr)

    def reset_detarr(self):
        """
        Reset the detector array structure.
        """
        if hasattr(self, '_detarr') and self._detarr is not None:
            qp.qp_free_detarr(self._detarr)
        self._detarr = None
        self.depo.pop('tod', None)
        self.depo.pop('flag', None)

    def reset(self):
        """
        Reset the internal data structures, and clear the data depo.
        """
        if not hasattr(self, 'depo'):
            self.depo = dict()
        self.reset_source()
        self.reset_dest()
        self.reset_point()
        self.reset_detarr()
        for k in self.depo:
            self.depo.pop(k)

    def from_tod(self, q_off, tod=None, count_hits=True, weight=None,
                 gain=None, poleff=None, flag=None, do_diff=False,
                 **kwargs):
        """
        Calculate signal and hits maps for given detectors.

        Arguments
        ---------
        q_off : array_like
          quaternion offset array, of shape (ndet, 4)
        tod : array_like, optional
          output array for timestreams, of shape (ndet, nsamp)
          if not supplied, only the projection map is populated.
        count_hits : bool, optional
          if True (default), populate projection map.
        weight : array_like, optional
          array of channel weights, of shape (ndet,).  Defaults to 1 if not
          supplied.
        gain : array_like, optional
            Per-channel gains, of shape (ndet,) or a constant.
            Default : 1.
        poleff : array_like, optional
          array of polarization efficiencies, of shape (ndet,).  Defaults to 1
          if not supplied.
        flag : array_like, optional
          array of flag timestreams for each channel, of shape (ndet, nsamp).
        do_diff: do timestream differencing. Assumes first half of tods are
          one pair and the second half are the other.

        The remaining keyword arguments are passed to the QPoint.set method.

        Returns
        -------
        vec : array_like, optional
            binned signal map, if tod is supplied
        proj : array_like, optional
            binned projection matrix map, if count_hits is True
        """

        self.set(**kwargs)

        # initialize detectors
        self.init_detarr(q_off, weight=weight, gain=gain, poleff=poleff,
                         tod=tod, flag=flag, do_diff=do_diff)
        
        # check modes
        return_vec = True
        if tod is None or tod is False or self.depo['vec'] is False:
            return_vec = False
        return_proj = True
        if not count_hits or self.depo['proj'] is False:
            if return_vec is False:
                raise RuntimeError, 'Nothing to do'
            return_proj = False

        # cache modes
        dest = self._dest.contents
        vec_mode = dest.vec_mode
        if return_vec is False:
            dest.vec_mode = 0
        proj_mode = dest.proj_mode
        if return_proj is False:
            dest.proj_mode = 0

        # run
        if qp.qp_tod2map(self._memory, self._detarr, self._point, self._dest):
            raise RuntimeError, qp.qp_get_error_string(self._memory)

        # reset modes
        dest.vec_mode = vec_mode
        dest.proj_mode = proj_mode

        # clean up
        self.reset_detarr()

        # return
        ret = ()
        if return_vec:
            ret += (self.depo['vec'].squeeze(),)
        if return_proj:
            ret += (self.depo['proj'].squeeze(),)
        if len(ret) == 1:
            return ret[0]
        return ret

    def to_tod(self, q_off, gain=None, poleff=None, tod=None, flag=None, **kwargs):
        """
        Calculate signal TOD from source map for multiple channels.

        Arguments
        ---------
        q_off : array_like
          quaternion offset array, of shape (ndet, 4)
        gain : array_like, optional
            Per-channel gains, of shape (ndet,) or a constant.
            Default : 1.
        poleff : array_like, optional
          array of polarization efficiencies, of shape (ndet,).  Defaults to 1
          if not supplied.
        tod : array_like, optional
          output array for timestreams, of shape (ndet, nsamp)
          use this keyword argument for in-place computation.

        The remaining keyword arguments are passed to the QPoint.set method.

        Returns
        -------
        tod : array_like
          A timestream sampled from the input map for each requested detector.
          The output array shape is (ndet, nsamp).
        """

        self.set(**kwargs)

        # initialize detectors
        self.init_detarr(q_off, gain=gain, poleff=poleff, tod=tod, flag=flag,
                         write=True)

        # run
        if qp.qp_map2tod(self._memory, self._detarr, self._point, self._source):
            raise RuntimeError, qp.qp_get_error_string(self._memory)
        tod = self.depo.pop('tod')

        # clean up
        self.reset_detarr()

        # return
        return tod

    def proj_cond(self, proj=None, mode=None, partial=False):
        """
        Hits-normalized projection matrix condition number for
        each pixel.

        Arguments
        ---------
        proj : array_like
            Projection matrix, of shape (N*(N+1)/2, npix).
            If None, obtained from the depo.
        mode : {None, 1, -1, 2, -2, inf, -inf, 'fro'}, optional
            condition number order.  See `numpy.linalg.cond`.
            Default: None (2-norm from SVD)
        partial : bool, optional
            If True, the map is not checked to ensure a proper healpix nside.

        Returns
        -------
        cond : array_like
            Condition number of each pixel.
        """

        # check inputs
        if proj is None:
            proj = self.depo['proj']
        if proj is None or proj is False:
            raise ValueError, 'missing proj'
        proj, _, nmap = check_proj(proj, copy=True, partial=partial)
        nproj = len(proj)

        # normalize
        m = proj[0].astype(bool)
        proj[:, m] /= proj[0, m]
        proj[:, ~m] = np.inf

        # return if unpolarized
        if nmap == 1:
            return proj[0]

        # projection matrix indices
        idx = np.zeros((nmap, nmap), dtype=int)
        rtri, ctri = np.triu_indices(nmap)
        idx[rtri, ctri] = idx[ctri, rtri] = np.arange(nproj)

        # calculate for each pixel
        # faster if numpy.linalg handles broadcasting
        npv = np.__version__.split('.')
        if len(npv)>3:
            if 'dev' in npv[-1]:
                npv = [0,0,0]
            else:
                npv = np.version.short_version.split('.')
        npv = map(int, npv)
        if npv >= [1,10,0]:
            proj[:, ~m] = 0
            cond = np.linalg.cond(proj[idx].transpose(2,0,1), p=mode)
            cond[~m] = np.inf
            # threshold at machine precision
            cond[cond > 1./np.finfo(float).eps] = np.inf
            return cond

        # slow method, loop over pixels
        def func(x):
            if not np.isfinite(x[0]):
                return np.inf
            c = np.linalg.cond(x[idx], p=mode)
            # threshold at machine precision
            if c > 1./np.finfo(float).eps:
                return np.inf
            return c
        cond = np.apply_along_axis(func, 0, proj)
        return cond

    def solve_map(self, vec=None, proj=None, mask=None, copy=True,
                  return_proj=False, return_mask=False, partial=None,
                  fill=0, cond=None, method='exact'):
        """
        Solve for a map, given the binned map and the projection matrix
        for each pixel.

        Arguments
        ---------
        vec : array_like, optional
            A map or list of N maps.  Default to `depo['vec']`.
        proj : array_like, optional
            An array of upper-triangular projection matrices for each pixel,
            of shape (N*(N+1)/2, npix).  Default to `depo['proj']`.
        mask : array_like, optional
            A mask of shape (npix,), evaluates to True where pixels are valid.
            The input mask in converted to a boolean array if supplied.
        copy : bool, optional
            if False, do the computation in-place so that the input maps are
            modified.  Otherwise, a copy is created prior to solving.
            Default: False.
        return_proj : bool, optional
            if True, return the Cholesky-decomposed projection matrix.
            if False, and inplace is True, the input projection matrix
            is not modified.
        return_mask : bool, optional
            if True, return the mask array, updated with any pixels
            that could not be solved.
        partial : bool, optional
            If True, the map is not checked to ensure a proper healpix nside.
        fill : scalar, optional
            Fill the solved map where proj == 0 with this value.  Default: 0.
        method : string, optional
            Map inversion method.  If "exact", invert the pointing matrix directly
            If "cho", use Cholesky decomposition to solve.  Default: "exact".

        Returns
        -------
        map : array_like
            A solved map or set of maps, in shape (N, npix).
        proj_out : array_like
            The upper triangular elements of the decomposed projection matrix,
            (if method is 'cho') or of the matrix inverse (if method is 'exact'),
            if requested, in shape (N*(N+1)/2, npix).
        mask : array_like
            1-d array, True for valid pixels, if `return_mask` is True
        """

        # check if we're dealing with a partial map
        if partial is None:
            if vec is None and 'dest_pixels' in self.depo:
                partial = True
            else:
                partial = False

        # ensure properly shaped arrays
        if vec is None:
            vec = self.depo['vec']
        if vec is None or vec is False:
            raise ValueError, 'missing vec'
        vec, nside = check_map(vec, copy=copy, partial=partial)

        if proj is None:
            proj = self.depo['proj']
        if proj is None or proj is False:
            raise ValueError, 'missing proj'
        pcopy = True if not return_proj else copy
        proj, pnside, nmap = check_proj(proj, copy=pcopy, partial=partial)

        if pnside != nside or nmap != len(vec):
            raise ValueError('vec and proj have incompatible shapes')
        nproj = len(proj)

        # deal with mask
        if mask is None:
            mask = np.ones(len(vec[0]), dtype=bool)
        else:
            mcopy = True if not return_mask else copy
            mask, mnside = check_map(mask, copy=mcopy, partial=partial)
            if mnside != nside:
                raise ValueError('mask has incompatible shape')
            mask = mask.squeeze().astype(bool)
        mask &= proj[0].astype(bool)

        # if unpolarized, just divide
        if len(vec) == 1:
            vec = vec.squeeze()
            proj = proj.squeeze()
            vec[mask] /= proj[mask]
            vec[~mask] = fill
            ret = (vec,) + (proj,) * return_proj + (mask,) * return_mask
            if len(ret) == 1:
                return ret[0]
            return ret

        # projection matrix indices
        idx = np.zeros((nmap, nmap), dtype=int)
        rtri, ctri = np.triu_indices(nmap)
        idx[rtri, ctri] = idx[ctri, rtri] = np.arange(nproj)

        # solve
        # faster if numpy.linalg handles broadcasting
        if method == 'exact' and map(int, 
                np.version.short_version.split('.')) >= [1,8,0]:
            if cond is None:
                cond = self.proj_cond(proj=proj)
            mask &= np.isfinite(cond)
            vec[:, ~mask] = 0
            proj[..., ~mask] = np.array([1,0,0,1,0,1])[:, None]
            vec[:] = np.linalg.solve(proj[idx].transpose(2,0,1),
                                     vec.transpose()).transpose()
            vec[:, ~mask] = fill
            proj[:, ~mask] = 0
            ret = (vec,) + return_proj * (proj,) + return_mask * (mask,)
            if len(ret) == 1:
                return ret[0]
            return ret

        # slow method, loop over pixels
        from scipy.linalg import cho_factor, cho_solve
        for ii, (m, A, v) in enumerate(zip(mask, proj[idx].T, vec.T)):
            if not m:
                proj[:, ii] = 0
                vec[:, ii] = fill
                continue
            try:
                if method == 'cho':
                    vec[:, ii] = cho_solve(cho_factor(A, False, True), v, True)
                elif method == 'exact':
                    vec[:, ii] = np.linalg.solve(A, v)
            except:
                mask[ii] = False
                proj[:, ii] = 0
                vec[:, ii] = fill
            else:
                proj[:, ii] = A[rtri, ctri]

        # return
        ret = (vec,) + (proj,) * return_proj + (mask,) * return_mask
        if len(ret) == 1:
            return ret[0]
        return ret

    def solve_map_cho(self, *args, **kwargs):
        """
        Solve for a map, given the binned map and the projection matrix
        for each pixel, using Cholesky decomposition.  This method
        uses the scipy.linalg.cho_factor and scipy.linalg.cho_solve
        functions internally.

        Arguments
        ---------
        vec : array_like, optional
            A map or list of N maps.  Default to `depo['vec']`.
        proj : array_like, optional
            An array of upper-triangular projection matrices for each pixel,
            of shape (N*(N+1)/2, npix).  Default to `depo['proj']`.
        mask : array_like, optional
            A mask of shape (npix,), evaluates to True where pixels are valid.
            The input mask in converted to a boolean array if supplied.
        copy : bool, optional
            if False, do the computation in-place so that the input maps are
            modified.  Otherwise, a copy is created prior to solving.
            Default: False.
        return_proj : bool, optional
            if True, return the Cholesky-decomposed projection matrix.
            if False, and inplace is True, the input projection matrix
            is not modified.
        return_mask : bool, optional
            if True, return the mask array, updated with any pixels
            that could not be solved.
        partial : bool, optional
            If True, the map is not checked to ensure a proper healpix nside.
        fill : scalar, optional
            Fill the solved map where proj == 0 with this value.  Default: 0.

        Returns
        -------
        map : array_like
            A solved map or set of maps, in shape (N, npix).
        proj_out : array_like
            The upper triangular elements of the decomposed projection matrix,
            if requested, in shape (N*(N+1)/2, npix).
        mask : array_like
            1-d array, True for valid pixels, if `return_mask` is True
        """
        kwargs['method'] = 'cho'
        return self.solve_map(*args, **kwargs)
