"""qpoint

A lightweight library for efficient pointing.

Based on M. Nolta's libactpol.
Uses the SOFA Software Collection, available from http://www.iausofa.org/
"""

import numpy as _np
from _libqpoint import libqp as _libqp, QP_DO_ALWAYS, QP_DO_ONCE, QP_DO_NEVER

class QPoint(object):
    
    def __init__(self, **kwargs):
        """
        Initialize a QPoint memory instance for keeping track of pointing
        corrections over time.
        
        Any keyword arguments are passed to QPoint.set to update memory.
        """
        
        # initialize memory
        self._memory = _libqp.qp_init_memory()
        
        # collect all parameter functions
        from _libqpoint import qp_funcs
        self._funcs = qp_funcs
        self._all_funcs = dict()
        for k,v in qp_funcs.items():
            self._all_funcs.update(**v)
        
        # set any requested parameters
        self.set(**kwargs)
        
    def __del__(self):
        """
        Free memory before deleting the object
        """
        _libqp.qp_free_memory(self._memory)
    
    def _set(self, key, val):
        """
        Set a single parameter to the given value.  See QPoint.set for a list
        of parameter names.
        """
        if key not in self._all_funcs:
            raise KeyError,'Unknown parameter %s' % key
        val = self._all_funcs[key]['check_set'](val)
        self._all_funcs[key]['set'](self._memory, val)
    
    def _get(self, key):
        """
        Get the value for a single parameter.  See QPoint.set for a list of
        parameter names.
        """
        if key not in self._all_funcs:
            raise KeyError,'Unknown parameter %s' % key
        val = self._all_funcs[key]['get'](self._memory)
        return self._all_funcs[key]['check_get'](val)
    
    def _check_input(self, name, arg, shape=None, dtype=_np.double, inplace=True,
                     fill=0):
        if arg is None:
            if shape is None:
                raise ValueError,'need shape to initialize input!'
            arg = _np.empty(shape, dtype=dtype)
            if fill is not None:
                arg[:] = fill
        if not isinstance(arg, _np.ndarray):
            raise TypeError,'input %s must be of type numpy.ndarray' % name
        if arg.dtype != dtype:
            arg = arg.astype(dtype)
        if shape is not None:
            if arg.shape != shape:
                raise ValueError,'input %s must have shape %s' % (name, shape)
        arg = _np.ascontiguousarray(arg)
        if inplace:
            return arg
        return arg.copy()

    def _check_output(self, name, arg=None, shape=None, dtype=_np.double,
                      fill=None, **kwargs):
        if arg is None:
            arg = kwargs.pop(name, None)
        if arg is None:
            if shape is None:
                raise KeyError,'need shape to initialize output!'
            arg = _np.empty(shape, dtype=dtype)
            if fill is not None:
                arg[:] = fill
        return self._check_input(name, arg, shape, dtype)

    def set(self, **kwargs):
        """
        Available keywords are:
        
        * Correction rates:
          NB: these can be 'never' (-999), 'once' (-1), 'always' (0) or seconds
        rate_daber     Rate at which the diurnal aberration correction is
                       applied (NB: this can only be applied always or never)
        rate_lonlat    Rate at which observer's lon and lat are updated
        rate_wobble    Rate at which the polar motion correction is updated
                       (NB: these are not estimated for dates beyond a year
                       from now)
        rate_dut1      Rate at which the ut1-utc correction is updated
                       (NB: this is not estimated for dates beyond a year from
                       now)
        rate_erot      Rate at which the earth's rotation angle is updated
        rate_npb       Rate at which the nutation/precession/frame-bias terms
                       are updated
        rate_aaber     Rate at which the annual aberration correction
                       (due to the earth's orbital velocity) is updated
        rate_ref       Rate at which the refaction correction is updated
                       (NB: this correction can also be updated manually -- see
                       refraction)
    
        * Options:
        accuracy       If 'low', use a truncated form (2000b) for the NPB 
                       correction, which is much faster but less accurate.
                       If 'high' (default), use the full 2006/2000a form.
        mean_aber      If True, apply the aberration correction as an average
                       for the entire field of view.  This is gives a 1-2
                       arcsec deviation at the edges of the SPIDER field of
                       view.
        fast_math      If True, use polynomial approximations for trig
                       functions
        polconv        Specify the 'cosmo' or 'iau' polarization convention
        pair_dets      If True, A/B detectors are paired in bore2map
                       (factor of 2 speed up in computation, but assumes ideality)
        pix_order      'nest' or 'ring' for healpix pixel ordering
        fast_pix       If True, use vec2pix to get pixel number directly from
                       the quaternion instead of ang2pix from ra/dec.
        num_threads    Number of threads for openMP bore2map computation
        
        * Weather:
        height         height above sea level, meters
        temperature    temperature, Celcius
        pressure       pressure, mbar
        humidity       relative humidity, fraction
        frequency      observer frequency, GHz
        lapse_rate     tropospheric lapse rate, K/m
        
        * Parameters:
        dut1           UT1 correction
        ref_tol        Tolerance on refraction correction, in radians
        ref_delta      Refraction correction
        """
        
        for k,v in kwargs.items():
            self._set(k ,v)
    
    def get(self,*args):
        """
        Returns a dictionary of the requested state parameters.  If no
        parameters are supplied, then all are returned.  If a single parameter
        is supplied, then just that value is returned.  See QPoint.set for a
        list of parameter names.
        
        Can also select 'options', 'rates', 'weather', or 'params' to return
        all of that subset of parameters.
        """
        state = dict()
        if not len(args):
            for k in self._funcs:
                state[k] = dict()
                for kk in self._funcs[k]:
                    state[k][kk] = self._get(kk)
            return state
        
        for arg in args:
            if arg in self._funcs:
                state[arg] = dict()
                for k in self._funcs[arg]:
                    state[arg][k] = self._get(k)
            else:
                state[arg] = self._get(arg)
        if len(args) == 1:
            return state[args[0]]
        return state
    
    def reset_rates(self):
        """
        Reset update counters for each state.  Useful to force an updated
        correction term at the beginning of each chunk.
        """
        _libqp.qp_reset_rates(self._memory)
    
    def refraction(self, *args, **kwargs):
        """
        Update refraction parameters
        
        Arguments (positional or keyword):
        
        q            observer orientation in horizon coordinates
        lat          latitude, degrees
        height       height above sea level, meters
        temperature  temperature, Celcius
        pressure     pressure, mbar
        humidity     humidity, fraction
        frequency    array frequency, GHz
        lapse_rate   tropospheric lapse rate, K/m
        tolerance    tolerance on convergence, radians
        delta        the refraction correction itself, in degrees
        
        If both el and lat are given, then the refraction correction in degrees
        is calculated, stored and returned after updating any other given
        parameters. Otherwise, the correction is returned w/out recalculating.
        
        Alternatively, if a single numerical argument, or the 'delta' keyword
        argument is given, then the correction is stored with this value
        instead of being recalculated.
        
        Numpy-vectorized for el and lat arguments.  Note that this is not
        an efficient vectorization, and only the last calculated value is
        stored for use in the coordinate conversion functions.
        """
        
        if len(args) == 1 and len(kwargs) == 0:
            v = args[0]
            self._set('ref_delta', v)
            return v
        
        if 'delta' in kwargs:
            v = kwargs.get('delta')
            self._set('ref_delta', v)
            return v
        
        arg_names = ['q','lat'] + self._funcs['weather'].keys()
        for idx,a in enumerate(args):
            kwargs[arg_names[idx]] = a
        
        for w in self._funcs['weather']:
            if w in kwargs:
                self._set(w, kwargs.get(w))

        q = kwargs.get('q',None)
        lat = kwargs.get('lat',None)
        if q is not None and lat is not None:
            def func(x0, x1, x2, x3, y):
                q = _np.ascontiguousarray([x0,x1,x2,x3])
                return _libqp.qp_update_ref(self._memory, q, y)
            fvec = _np.vectorize(func,[_np.double])
            if q.size / 4 > 1:
                q = q.transpose()
            delta = fvec(q[0], q[1], q[2], q[3], lat)
            if delta.shape == ():
                return delta[()]
            return delta
        return self._get('ref_delta')

    def gmst(self, ctime, **kwargs):
        """
        Return Greenwich mean sidereal time for given ctimes and longitudes.
        Vectorized.

        Arguments:

        ctime      unix time in seconds UTC

        Keyword arguments:

        Any keywords accepted by the QPoint.set function can also be passed
        here, and will be processed prior to calculation.

        Outputs:

        gmst       Greenwich mean sidereal time of the observer
        """

        self.set(**kwargs)

        ctime = self._check_input('ctime', _np.atleast_1d(ctime))

        if ctime.size == 1:
            return _libqp.qp_gmst(self._memory, ctime[0])

        gmst = self._check_output('gmst', shape=ctime.shape)
        _libqp.qp_gmstn(self._memory, ctime, gmst, ctime.size)
        return gmst

    def lmst(self, ctime, lon, **kwargs):
        """
        Return local mean sidereal time for given ctimes and longitudes.
        Vectorized.
        
        Arguments:
        
        ctime      unix time in seconds UTC
        lon        observer longitude (degrees)
        
        Keyword arguments:
        
        Any keywords accepted by the QPoint.set function can also be passed
        here, and will be processed prior to calculation.
        
        Outputs:
        
        lmst       local mean sidereal time of the observer
        """
        
        self.set(**kwargs)
        
        ctime = self._check_input('ctime', _np.atleast_1d(ctime))
        lon = self._check_input('lon', _np.atleast_1d(lon), shape=ctime.shape)
        
        if ctime.size == 1:
            return _libqp.qp_lmst(self._memory, ctime[0], lon[0])
        
        lmst = self._check_output('lmst', shape=ctime.shape)
        _libqp.qp_lmstn(self._memory, ctime, lon, lmst, ctime.size)
        return lmst
        
    def dipole(self, ctime, ra, dec, **kwargs):
        """
        Return dipole amplitude in the given equatorial direction.
        Vectorized.

        Arguments:

        ctime      unix time in seconds UTC
        ra         right ascension on the sky
        dec        declination on the sky

        Keyword arguments:

        Any keywords accepted by the QPoint.set function can also be passed
        here, and will be processed prior to calculation.

        Outputs:

        dipole     dipole amplitude in K
        """

        self.set(**kwargs)

        ctime = self._check_input('ctime', _np.atleast_1d(ctime))
        ra = self._check_input('ra', _np.atleast_1d(ra), shape=ctime.shape)
        dec = self._check_input('dec', _np.atleast_1d(dec), shape=ctime.shape)

        if ctime.size == 1:
            return _libqp.qp_dipole(self._memory, ctime[0], ra[0], dec[0])

        dipole = self._check_output('dipole', shape=ctime.shape)
        _libqp.qp_dipolen(self._memory, ctime, ra, dec, dipole, ctime.size)
        return dipole

    def det_offset(self, delta_az, delta_el, delta_psi):
        """
        Return quaternion corresponding to the requested detector offset.
        Vectorized.
        
        Arguments:
        
        delta_az   azimuthal offset of the detector (degrees)
        delta_el   elevation offset of the detector (degrees)
        delta_psi  polarization offset of the detector (degrees)
        
        Outputs:
        
        q          detector offset quaternion for each detector
        """
        
        delta_az, delta_el, delta_psi \
            = [self._check_input('offset', _np.atleast_1d(x))
               for x in _np.broadcast_arrays(delta_az, delta_el, delta_psi)]
        ndet = delta_az.size
        
        for x in (delta_el, delta_psi):
            if x.shape != delta_az.shape:
                raise ValueError, "input offset vectors must have the same shape"
        
        if ndet == 1:
            quat = self._check_output('quat', shape=(4,))
            _libqp.qp_det_offset(delta_az[0], delta_el[0], delta_psi[0], quat)
        else:
            quat = self._check_output('quat', shape=(ndet,4))
            _libqp.qp_det_offsetn(delta_az, delta_el, delta_psi, quat, ndet)
        
        return quat
        
    def hwp_quat(self, theta):
        """
        Return quaternion corresponding to rotation by 2*theta,
        where theta is the physical waveplate angle.
        Vectorized.
        
        Arguments:
        
        theta      hwp physical angle (degrees)
        
        Outputs:
        
        q          quaternion for each hwp angle
        """
        theta = self._check_input('theta', _np.atleast_1d(theta))
        if theta.size == 1:
            quat = self._check_output('quat', shape=(4,))
            _libqp.qp_hwp_quat(theta[0], quat)
        else:
            quat = self._check_output('quat', shape=(theta.size,4))
            _libqp.qp_hwp_quatn(theta, quat, theta.size)
        return quat
    
    def azel2bore(self, az, el, pitch, roll, lon, lat, ctime, q=None,
                  **kwargs):
        """
        Estimate the quaternion for the boresight orientation on the sky given
        the attitude (az/el/pitch/roll), location on the earth (lon/lat) and
        ctime. Input vectors must be numpy-array-like and of the same shape.
        
        Arguments:
        
        az         boresight azimuth (degrees)
        el         boresight elevation (degrees)
        pitch      boresight pitch (degrees); can be None
        roll       boresight pitch (degrees); can be None
        lon        observer longitude (degrees)
        lat        observer latitude (degrees)
        ctime      unix time in seconds UTC
        q          output quaternion array initialized by user
        
        Keywork arguments:

        Any keywords accepted by the QPoint.set function can also be passed
        here, and will be processed prior to calculation.
        
        Output:
        
        q          Nx4 numpy array of quaternions for each supplied timestamp.
        """
        
        self.set(**kwargs)
        
        az    = self._check_input('az', az)
        el    = self._check_input('el',    el,    shape=az.shape)
        pitch = self._check_input('pitch', pitch, shape=az.shape, fill=0)
        roll  = self._check_input('roll',  roll,  shape=az.shape, fill=0)
        lon   = self._check_input('lon',   lon,   shape=az.shape)
        lat   = self._check_input('lat',   lat,   shape=az.shape)
        ctime = self._check_input('ctime', ctime, shape=az.shape)
        n = az.size

        # identity quaternion
        q = self._check_output('q', q, shape=(n,4), fill=0)
        if _np.all(q==0):
            q[:,0] = 1

        _libqp.qp_azel2bore(self._memory, az, el, pitch, roll, lon, lat,
                            ctime, q, n)
        
        return q
    
    def bore2radec(self, q_off, ctime, q_bore, q_hwp=None, sindec=False,
                   ra=None, dec=None, sin2psi=None, cos2psi=None, **kwargs):
        """
        Calculate the orientation on the sky for a detector offset from the
        boresight.  Detector offsets are defined assuming the boresight is
        pointed toward the horizon, and that the boresight polarization axis is
        along the vertical.
        
        Arguments:
        
        q_off      Detector offset quaternion for a single detector,
                   calculated using det_offset
        ctime      array of unix times in seconds UTC
        q_bore     Nx4 array of quaternions encoding the boresight orientation 
                   on the sky (as output by azel2radec)
        
        Keyword arguments:
        
        q_hwp      HWP angle quaternions calculated using hwp_quat
                   must be same shape as q_bore
        sindec     If True, return sin(dec) instead of dec in degrees
                   (default False)
        
        Any keywords accepted by the QPoint.set function can also be passed
        here, and will be processed prior to calculation.    
        
        Outputs:
        
        ra         detector right ascension (degrees)
        dec/sindec detector declination (degrees) or sin(dec)
        sin2psi    detector polarization orientation
        cos2psi    detector polarization orientation
        """
        
        self.set(**kwargs)
        
        q_off  = self._check_input('q_off', q_off)
        ctime  = self._check_input('ctime', ctime)
        q_bore = self._check_input('q_bore', q_bore, shape=ctime.shape+(4,))
        ra = self._check_output('ra', ra, shape=ctime.shape, dtype=_np.double)
        dec = self._check_output('dec', dec, shape=ctime.shape, dtype=_np.double)
        sin2psi = self._check_output('sin2psi', sin2psi, shape=ctime.shape,
                                     dtype=_np.double)
        cos2psi = self._check_output('cos2psi', cos2psi, shape=ctime.shape,
                                     dtype=_np.double)
        n = ctime.size
        
        if q_hwp is None:
            if sindec:
                _libqp.qp_bore2rasindec(self._memory, q_off, ctime, q_bore,
                                        ra, dec, sin2psi, cos2psi, n)
            else:
                _libqp.qp_bore2radec(self._memory, q_off, ctime, q_bore,
                                     ra, dec, sin2psi, cos2psi, n)
        else:
            q_hwp = self._check_input('q_hwp', q_hwp, shape=q_bore.shape)
            if sindec:
                _libqp.qp_bore2rasindec_hwp(self._memory, q_off, ctime, q_bore,
                                            q_hwp, ra, dec, sin2psi, cos2psi, n)
            else:
                _libqp.qp_bore2radec_hwp(self._memory, q_off, ctime, q_bore,
                                         q_hwp, ra, dec, sin2psi, cos2psi, n)
        
        return ra, dec, sin2psi, cos2psi
    
    def azel2radec(self, delta_az, delta_el, delta_psi,
                   az, el, pitch, roll, lon, lat, ctime,
                   hwp=None, sindec=False, ra=None, dec=None,
                   sin2psi=None, cos2psi=None, **kwargs):
        """
        Estimate the orientation on the sky for a detector offset from
        boresight, given the boresight attitude (az/el/pitch/roll), location on
        the earth (lon/lat) and UTC time.  Input vectors must be
        numpy-array-like and of the same shape. Detector offsets are defined
        assuming the boresight is pointed toward the horizon, and that the
        boresight polarization axis is along the horizontal.
        
        Arguments:
        
        delta_az   azimuthal offset of the detector (degrees)
        delta_el   elevation offset of the detector (degrees)
        delta_psi  polarization offset of the detector (degrees)
        az         boresight azimuth (degrees)
        el         boresight elevation (degrees)
        pitch      boresight pitch (degrees); can be None
        roll       boresight roll (degrees); can be None
        lon        observer longitude (degrees)
        lat        observer latitude (degrees)
        ctime      unix time in seconds UTC
        
        Keyword arguments:
        
        hwp        HWP angles (degrees)
        sindec     If True, return sin(dec) instead of dec in degrees
                   (default False)
        
        Any keywords accepted by the QPoint.set function can also be passed
        here, and will be processed prior to calculation.    
        
        Outputs:
        
        ra         detector right ascension (degrees)
        dec/sindec detector declination (degrees)
        sin2psi    detector polarization orientation
        cos2psi    detector polarization orientation
        """
        
        self.set(**kwargs)
        
        az    = self._check_input('az', az)
        el    = self._check_input('el',    el,    shape=az.shape)
        pitch = self._check_input('pitch', pitch, shape=az.shape, fill=0)
        roll  = self._check_input('roll',  roll,  shape=az.shape, fill=0)
        lon   = self._check_input('lon',   lon,   shape=az.shape)
        lat   = self._check_input('lat',   lat,   shape=az.shape)
        ctime = self._check_input('ctime', ctime, shape=az.shape)
        ra = self._check_output('ra', ra, shape=az.shape, dtype=_np.double)
        dec = self._check_output('dec', dec, shape=az.shape, dtype=_np.double)
        sin2psi = self._check_output('sin2psi', sin2psi, shape=az.shape,
                                     dtype=_np.double)
        cos2psi = self._check_output('cos2psi', cos2psi, shape=az.shape,
                                     dtype=_np.double)
        n = az.size
        
        if hwp is None:
            if sindec:
                _libqp.qp_azel2rasindec(self._memory, delta_az, delta_el, delta_psi,
                                        az, el, pitch, roll, lon, lat, ctime,
                                        ra, dec, sin2psi, cos2psi, n)
            else:
                _libqp.qp_azel2radec(self._memory, delta_az, delta_el, delta_psi,
                                     az, el, pitch, roll, lon, lat, ctime,
                                     ra, dec, sin2psi, cos2psi, n)
        else:
            hwp = self._check_input('hwp', hwp, shape=az.shape)

            if sindec:
                _libqp.qp_azel2rasindec_hwp(self._memory, delta_az, delta_el, delta_psi,
                                            az, el, pitch, roll, lon, lat, ctime, hwp,
                                            ra, dec, sin2psi, cos2psi, n)
            else:
                _libqp.qp_azel2radec_hwp(self._memory, delta_az, delta_el, delta_psi,
                                         az, el, pitch, roll, lon, lat, ctime, hwp,
                                         ra, dec, sin2psi, cos2psi, n)
        
        return ra, dec, sin2psi, cos2psi
        
    def radec2pix(self, ra, dec, nside=256, **kwargs):
        """
        Calculate healpix pixel number for given ra/dec and nside
        """

        self.set(**kwargs)

        ra    = self._check_input('ra', ra)
        dec   = self._check_input('dec', dec, shape=ra.shape)

        if ra.size == 1:
            return _libqp.qp_radec2pix(self._memory, ra[0], dec[0], nside)

        pix = self._check_output('pix', shape=ra.shape, dtype=_np.int)
        _libqp.qp_radec2pixn(self._memory, ra, dec, nside, pix, ra.size)
        return pix

    def quat2pix(self, quat, nside=256, **kwargs):
        """
        Calculate healpix pixel number and polarization angle given
        quaternion and nside
        """

        self.set(**kwargs)

        quat = self._check_input('quat', quat)
        if quat.size / 4 == 1:
            from _libqpoint import quat2pix
            return quat2pix(self._memory, quat, nside)

        n = quat.shape[0]
        shape = (n,)
        pix = self._check_output('pix', shape=shape, dtype=_np.int, **kwargs)
        sin2psi = self._check_output('sin2psi', shape=shape, **kwargs)
        cos2psi = self._check_output('cos2psi', shape=shape, **kwargs)
        _libqp.qp_quat2pixn(self._memory, quat, nside, pix, sin2psi, cos2psi, n)
        return pix, sin2psi, cos2psi

    def bore2pix(self, q_off, ctime, q_bore, q_hwp=None, nside=256, **kwargs):
        """
        Calculate the orientation on the sky for a detector offset from the
        boresight.  Detector offsets are defined assuming the boresight is
        pointed toward the horizon, and that the boresight polarization axis is
        along the vertical.

        Arguments:

        q_off      Detector offset quaternion for a single detector,
                   calculated using det_offset
        ctime      array of unix times in seconds UTC
        q_bore     Nx4 array of quaternions encoding the boresight orientation
                   on the sky (as output by azel2radec)

        Keyword arguments:

        q_hwp      HWP angle quaternions calculated using hwp_quat
                   must be same shape as q_bore
        nside      map dimension

        Any keywords accepted by the QPoint.set function can also be passed
        here, and will be processed prior to calculation.

        Outputs:

        pix        detector pixel number
        sin2psi    detector polarization orientation
        cos2psi    detector polarization orientation
        """

        self.set(**kwargs)

        q_off  = self._check_input('q_off', q_off)
        ctime  = self._check_input('ctime', ctime)
        q_bore = self._check_input('q_bore', q_bore, shape=ctime.shape+(4,))
        pix  = self._check_output('pix', shape=ctime.shape,
                                  dtype=_np.int, **kwargs)
        sin2psi = self._check_output('sin2psi', shape=ctime.shape,
                                     **kwargs)
        cos2psi = self._check_output('cos2psi', shape=ctime.shape,
                                     **kwargs)
        n = ctime.size

        if q_hwp is None:
            _libqp.qp_bore2pix(self._memory, q_off, ctime, q_bore,
                               nside, pix, sin2psi, cos2psi, n)
        else:
            q_hwp = self._check_input('q_hwp', q_hwp, shape=q_bore.shape)

            _libqp.qp_bore2pix_hwp(self._memory, q_off, ctime, q_bore,
                                   q_hwp, nside, pix, sin2psi, cos2psi, n)

        return pix, sin2psi, cos2psi

    def bore2map(self, q_off, ctime, q_bore, nside=256,
                 q_hwp=None, tod=None, smap=None, pmap=None, **kwargs):
        """
        Calculate signal and hits maps for given detectors and boresight orientations.
        Returns an npix-x-3 array containing (d, d*cos(2 psi), d*sin(2 psi)), and
        an npix-x-6 array containing (hits, p01, p02, p11, p12, p22).
        If either smap or pmap is False, then that map is not computed or returned.
        If tod is not supplied then smap is not computed.
        tod must be an array of shape (ndet, ntod).
        Optionally accumulate hits in place by supplying an existing smap and pmap array.
        """
        
        self.set(**kwargs)
        
        q_off = self._check_input('q_off', q_off)
        ndet = q_off.size/4
        
        ctime  = self._check_input('ctime', ctime)
        q_bore = self._check_input('q_bore', q_bore, shape=ctime.shape+(4,))
        n = ctime.size
        
        do_pnt = not (pmap is False)
        do_sig = not (tod is None or tod is False or smap is False)

        if not (do_pnt or do_sig):
            raise KeyError, 'Either smap or pmap must not be False'

        mshapep = (12*nside*nside, 6)
        
        if do_pnt:
            if pmap is None:
                pmap = _np.zeros(mshapep, dtype=_np.double)
            else:
                nside = int(_np.sqrt(pmap.size/6/12))
                mshapep = (12*nside*nside, 6)
            self._check_output('pmap', pmap, shape=mshapep)

        mshapes = (12*nside*nside, 3)

        if do_sig:
            tod = self._check_input('tod', tod, shape=(ndet, n))
            todp = (tod.__array_interface__['data'][0] +
                    _np.arange(tod.shape[0]) * tod.strides[0]).astype(_np.uintp)

            if smap is None:
                smap = _np.zeros(mshapes, dtype=_np.double)
            else:
                nside = int(_np.sqrt(smap.size/3/12))
                mshapes = (12*nside*nside, 3)
            self._check_output('smap', smap, shape=mshapes)

        if q_hwp is None:
            if do_pnt and do_sig:
                _libqp.qp_bore2sigpnt(self._memory, q_off, ndet, ctime, q_bore, todp, n,
                                      smap, pmap, nside)
                ret = (smap, pmap)
            elif do_sig:
                _libqp.qp_bore2sig(self._memory, q_off, ndet, ctime, q_bore, todp, n,
                                   smap, nside)
                ret = smap
            elif do_pnt:
                _libqp.qp_bore2pnt(self._memory, q_off, ndet, ctime, q_bore, n,
                                   pmap, nside)
                ret = pmap
        else:
            q_hwp = self._check_input('q_hwp', q_hwp, shape=q_bore.shape)
            
            if do_pnt and do_sig:
                _libqp.qp_bore2sigpnt_hwp(self._memory, q_off, ndet, ctime, q_bore,
                                          q_hwp, todp, n, smap, pmap, nside)
                ret = (smap, pmap)
            elif do_sig:
                _libqp.qp_bore2sig_hwp(self._memory, q_off, ndet, ctime, q_bore,
                                       q_hwp, todp, n, smap, nside)
                ret = smap
            elif do_pnt:
                _libqp.qp_bore2pnt_hwp(self._memory, q_off, ndet, ctime, q_bore,
                                       q_hwp, n, pmap, nside)
                ret = pmap

        return ret
        
    def map2tod(self, q_off, ctime, q_bore, smap, q_hwp=None, tod=None,
                **kwargs):
        """
        Calculate signal TOD from input map given detector offsets,
        boresight orientation and hwp orientation (optional).
        Input smap is an npix-x-N array containing (T,Q,U) maps and
        possibly their derivatives.

        N    smap contents
        ------------------
        3    (T, Q, U)
        9    + (dTdtheta, dQdtheta, dUdtheta, dTdphi, dQdphi, dUdphi)
        18   + (dT2dt2, dQ2dt2, dU2dt2, dT2dpdt, dQ2dpdt, dU2dpdt,
                dT2dp2, dQ2dp2, dU2dp2)

        Returns an array of shape (ndet, nsamp).
        """

        self.set(**kwargs)

        q_off = self._check_input('q_off', q_off)
        ndet = q_off.size/4

        ctime  = self._check_input('ctime', ctime)
        q_bore = self._check_input('q_bore', q_bore, shape=ctime.shape+(4,))
        n = ctime.size

        npix = max(smap.shape)
        nside = _np.sqrt(npix / 12)
        if _np.floor(_np.log2(nside)) != _np.log2(nside):
            raise ValueError,'invalid nside'
        nside = int(nside)
        ncol = smap.size / npix
        if smap.shape == (ncol, npix):
            smap = self._check_output('smap', smap.transpose(), shape=(npix, ncol))

        if ncol not in [3,9,18]:
            raise ValueError,'map must have 3,9 or 18 columns'

        self._check_output('tod', tod, shape=(ndet, n))
        # array of pointers
        todp = (tod.__array_interface__['data'][0] +
                _np.arange(tod.shape[0]) * tod.strides[0]).astype(_np.uintp)

        if ncol == 3:
            if q_hwp is None:
                _libqp.qp_map2tod(self._memory, q_off, ndet, ctime, q_bore,
                                  smap, nside, todp, n)
            else:
                q_hwp = self._check_input('q_hwp', q_hwp, shape=q_bore.shape)
                _libqp.qp_map2tod_hwp(self._memory, q_off, ndet, ctime, q_bore, q_hwp,
                                      smap, nside, todp, n)
        elif ncol == 9:
            if q_hwp is None:
                _libqp.qp_map2tod_der1(self._memory, q_off, ndet, ctime, q_bore,
                                       smap, nside, todp, n)
            else:
                q_hwp = self._check_input('q_hwp', q_hwp, shape=q_bore.shape)
                _libqp.qp_map2tod_der1_hwp(self._memory, q_off, ndet, ctime, q_bore,
                                           q_hwp, smap, nside, todp, n)
        elif ncol == 18:
            if q_hwp is None:
                _libqp.qp_map2tod_der2(self._memory, q_off, ndet, ctime, q_bore,
                                       smap, nside, todp, n)
            else:
                q_hwp = self._check_input('q_hwp', q_hwp, shape=q_bore.shape)
                _libqp.qp_map2tod_der2_hwp(self._memory, q_off, ndet, ctime, q_bore,
                                           q_hwp, smap, nside, todp, n)

        return tod

    def load_bulletin_a(self, filename, columns=['mjd','dut1','x','y'], **kwargs):
        """
        Load IERS Bulletin A from file and store in memory.  The file must be
        readable using numpy.loadtxt with unpack=True, and is assumed to be sorted
        by mjd.
        
        Keyword arguments:
        
        columns    list of columns as they appear in the file.
                   A KeyError is raise if the list does not contain
                   each of ['mjd', 'dut1', 'x', 'y']
        
        Any other keyword arguments are passed to the numpy.loadtxt function
        
        Output:
        
        mjd, dut1, x, y
        """
        
        req_columns = ['mjd','dut1','x','y']
        if not set(req_columns) <= set(columns):
            raise KeyError,\
                'Missing columns %s' % str(list(set(req_columns)-set(columns)))
        kwargs['unpack'] = True
        data = _np.loadtxt(filename, **kwargs)
        mjd, x, y, dut1 = (data[columns.index(x)] for x in req_columns)
        mjd_min, mjd_max = int(mjd[0]), int(mjd[-1])
        
        try:
            _libqp.set_iers_bulletin_a(self._memory, mjd_min, mjd_max, dut1, x, y)
        except:
            raise RuntimeError, \
                'Error loading Bulletin A data from file %s' % filename
        
        return mjd, dut1, x, y
    
    def get_bulletin_a(self, mjd):
        """
        Return dut1/x/y for given mjd. Numpy-vectorized.
        """
        
        from _libqpoint import get_bulletin_a
        def func(x): return get_bulletin_a(self._memory, x)
        fvec = _np.vectorize(func, [_np.double]*3)
        
        out = fvec(mjd)
        if out[0].shape == ():
            return tuple(x[()] for x in out)
        return out

def refraction(el, lat, height, temp, press, hum,
               freq=150., lapse=0.0065, tol=1e-8):
    """
    Standalone function for calculating the refraction correction without
    storing any parameters.  Useful for testing, numpy-vectorized.
    
    Arguments:
    
    el           elevation angle, degrees
    lat          latitude, degrees
    height       height above sea level, meters
    temperature  temperature, Celcius
    pressure     pressure, mbar
    humidity     humidity, fraction
    frequency    array frequency, GHz
    lapse_rate   tropospheric lapse rate, K/m
    tolerance    tolerance on convergence, radians
    
    Output:
    
    delta        refraction correction, in degrees
    """
    
    fvec = _np.vectorize(_libqp.qp_refraction,[_np.double])
    delta = fvec(el, lat, height, temp, press, hum, freq, lapse, tol)
    if delta.shape == ():
        return delta[()]
    return delta

# for debugging
def _plot_diff(ang1,ang2,asec=True,n=None):
    scale = 3600 if asec else 1
    if n is None:
        n = len(ang1[0])
    
    dra = (ang1[0]-ang2[0])*scale
    ddec = (ang1[1]-ang2[1])*scale
    ds2p = (ang1[2]-ang2[2])
    dc2p = (ang1[3]-ang2[3])
    
    import pylab
    pylab.figure();
    ax = pylab.subplot(411);
    pylab.plot(dra[:n]);
    pylab.subplot(412,sharex=ax);
    pylab.plot(ddec[:n]);
    pylab.subplot(413,sharex=ax);
    pylab.plot(ds2p[:n]);
    pylab.subplot(414,sharex=ax);
    pylab.plot(dc2p[:n]);
