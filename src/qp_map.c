#include <stdio.h>
#include <assert.h>
#include <stdlib.h>
#include "qpoint.h"
#include "fast_math.h"
#include "vec3.h"
#include "quaternion.h"
#include <chealpix.h>
#ifdef _OPENMP
#include <omp.h>
#endif

/* Compute healpix pixel number for given nside and ra/dec */
long qp_radec2pix(qp_memory_t *mem, int nside, double ra, double dec) {
  long pix;
  if (mem->pix_order == QP_ORDER_NEST)
    ang2pix_nest(nside, M_PI_2 - deg2rad(dec), deg2rad(ra), &pix);
  ang2pix_ring(nside, M_PI_2 - deg2rad(dec), deg2rad(ra), &pix);
  return pix;
}

void qp_radec2pixn(qp_memory_t *mem, int nside, double *ra, double *dec,
                   long *pix, int n) {
  for (int ii = 0; ii < n; ii++) {
    pix[ii] = qp_radec2pix(mem, nside, ra[ii], dec[ii]);
  }
}

/* Compute pointing matrix map for given boresight timestream and detector
   offset. pmap is a 6-x-npix array containing (hits, p01, p02, p11, p12, p22) */
void qp_bore2pnt_single(qp_memory_t *mem, quat_t q_off,
			double *ctime, quat_t *q_bore, int n,
			pixel_t *pmap, int nside) {
  double ra, dec, sin2psi, cos2psi;
  long ipix;
  quat_t q;
  
  for (int ii=0; ii<n; ii++) {
    qp_bore2det(mem, q_off, ctime[ii], q_bore[ii], q);
    qp_quat2radec(mem, q, &ra, &dec, &sin2psi, &cos2psi);
    ipix = qp_radec2pix(mem, nside, ra, dec);
    pmap[ipix][0] += 1;
    pmap[ipix][1] += cos2psi;
    pmap[ipix][2] += sin2psi;
    pmap[ipix][3] += cos2psi*cos2psi;
    pmap[ipix][4] += cos2psi*sin2psi;
    pmap[ipix][5] += sin2psi*sin2psi;
  }
}

/* Compute signal map for given boresight timestream, signal timestream,
   and detector offset.
   smap is a npix-x-3 array containing (d, d*cos(2 psi), d*sin(2 psi)). */
void qp_bore2sig_single(qp_memory_t *mem, quat_t q_off,
                        double *ctime, quat_t *q_bore, double *tod, int n,
                        vec3_t *smap, int nside) {
  double ra, dec, sin2psi, cos2psi;
  long ipix;
  quat_t q;

  for (int ii=0; ii<n; ii++) {
    qp_bore2det(mem, q_off, ctime[ii], q_bore[ii], q);
    qp_quat2radec(mem, q, &ra, &dec, &sin2psi, &cos2psi);
    ipix = qp_radec2pix(mem, nside, ra, dec);
    smap[ipix][0] += tod[ii];
    smap[ipix][1] += tod[ii] * cos2psi;
    smap[ipix][2] += tod[ii] * sin2psi;
  }
}

/* Compute signal and pointing matrix maps for given boresight timestream,
   signal timestream, and detector offset.
   smap is a npix-x-3 array containing (d, d*cos(2 psi), d*sin(2 psi)). */
void qp_bore2sigpnt_single(qp_memory_t *mem, quat_t q_off,
                           double *ctime, quat_t *q_bore, double *tod, int n,
                           vec3_t *smap, pixel_t *pmap, int nside) {
  double ra, dec, sin2psi, cos2psi;
  long ipix;
  quat_t q;

  for (int ii=0; ii<n; ii++) {
    qp_bore2det(mem, q_off, ctime[ii], q_bore[ii], q);
    qp_quat2radec(mem, q, &ra, &dec, &sin2psi, &cos2psi);
    ipix = qp_radec2pix(mem, nside, ra, dec);
    smap[ipix][0] += tod[ii];
    smap[ipix][1] += tod[ii] * cos2psi;
    smap[ipix][2] += tod[ii] * sin2psi;
    pmap[ipix][0] += 1;
    pmap[ipix][1] += cos2psi;
    pmap[ipix][2] += sin2psi;
    pmap[ipix][3] += cos2psi*cos2psi;
    pmap[ipix][4] += cos2psi*sin2psi;
    pmap[ipix][5] += sin2psi*sin2psi;
  }
}

/* Compute pointing matrix map for given boresight timestream and detector
   offset. pmap is a 6-x-npix array containing (hits, p01, p02, p11, p12, p22) */
void qp_bore2pnt_single_hwp(qp_memory_t *mem, quat_t q_off,
			    double *ctime, quat_t *q_bore, quat_t *q_hwp, int n,
			    pixel_t *pmap, int nside) {
  double ra, dec, sin2psi, cos2psi;
  long ipix;
  quat_t q;
  
  for (int ii=0; ii<n; ii++) {
    qp_bore2det_hwp(mem, q_off, ctime[ii], q_bore[ii], q_hwp[ii], q);
    qp_quat2radec(mem, q, &ra, &dec, &sin2psi, &cos2psi);
    ipix = qp_radec2pix(mem, nside, ra, dec);
    pmap[ipix][0] += 1;
    pmap[ipix][1] += cos2psi;
    pmap[ipix][2] += sin2psi;
    pmap[ipix][3] += cos2psi*cos2psi;
    pmap[ipix][4] += cos2psi*sin2psi;
    pmap[ipix][5] += sin2psi*sin2psi;
  }
}

/* Compute signal map for given boresight timestream, hwp timestream,
   signal timestream, and detector offset.
   smap is a npix-x-3 array containing (d, d*cos(2 psi), d*sin(2 psi)). */
void qp_bore2sig_single_hwp(qp_memory_t *mem, quat_t q_off,
                            double *ctime, quat_t *q_bore, quat_t *q_hwp,
                            double *tod, int n, vec3_t *smap, int nside) {
  double ra, dec, sin2psi, cos2psi;
  long ipix;
  quat_t q;

  for (int ii=0; ii<n; ii++) {
    qp_bore2det_hwp(mem, q_off, ctime[ii], q_bore[ii], q_hwp[ii], q);
    qp_quat2radec(mem, q, &ra, &dec, &sin2psi, &cos2psi);
    ipix = qp_radec2pix(mem, nside, ra, dec);
    smap[ipix][0] += tod[ii];
    smap[ipix][1] += tod[ii] * cos2psi;
    smap[ipix][2] += tod[ii] * sin2psi;
  }
}

/* Compute signal and pointing matrix maps for given boresight timestream,
   hwp timestream, signal timestream, and detector offset.
   smap is a npix-x-3 array containing (d, d*cos(2 psi), d*sin(2 psi)). */
void qp_bore2sigpnt_single_hwp(qp_memory_t *mem, quat_t q_off,
                               double *ctime, quat_t *q_bore, quat_t *q_hwp,
                               double *tod, int n, vec3_t *smap,
                               pixel_t *pmap, int nside) {
  double ra, dec, sin2psi, cos2psi;
  long ipix;
  quat_t q;

  for (int ii=0; ii<n; ii++) {
    qp_bore2det_hwp(mem, q_off, ctime[ii], q_bore[ii], q_hwp[ii], q);
    qp_quat2radec(mem, q, &ra, &dec, &sin2psi, &cos2psi);
    ipix = qp_radec2pix(mem, nside, ra, dec);
    smap[ipix][0] += tod[ii];
    smap[ipix][1] += tod[ii] * cos2psi;
    smap[ipix][2] += tod[ii] * sin2psi;
    pmap[ipix][0] += 1;
    pmap[ipix][1] += cos2psi;
    pmap[ipix][2] += sin2psi;
    pmap[ipix][3] += cos2psi*cos2psi;
    pmap[ipix][4] += cos2psi*sin2psi;
    pmap[ipix][5] += sin2psi*sin2psi;
  }
}

/* Compute pointing matrix map for given boresight timestream and detector
   pair. pmap is a 6-x-npix array containing (hits, p01, p02, p11, p12, p22) */
void qp_bore2pnt_pair(qp_memory_t *mem, quat_t q_off,
		      double *ctime, quat_t *q_bore, int n,
		      pixel_t *pmap, int nside) {
  double ra, dec, sin2psi, cos2psi;
  long ipix;
  quat_t q;
  
  for (int ii=0; ii<n; ii++) {
    qp_bore2det(mem, q_off, ctime[ii], q_bore[ii], q);
    qp_quat2radec(mem, q, &ra, &dec, &sin2psi, &cos2psi);
    ipix = qp_radec2pix(mem, nside, ra, dec);
    pmap[ipix][0] += 2;
    pmap[ipix][3] += 2*cos2psi*cos2psi;
    pmap[ipix][4] += 2*cos2psi*sin2psi;
    pmap[ipix][5] += 2*sin2psi*sin2psi;
  }
}

/* Compute pointing matrix map for given boresight timestream and detector
   pair. pmap is a 6-x-npix array containing (hits, p01, p02, p11, p12, p22) */
void qp_bore2pnt_pair_hwp(qp_memory_t *mem, quat_t q_off,
			  double *ctime, quat_t *q_bore, quat_t *q_hwp, int n,
			  pixel_t *pmap, int nside) {
  double ra, dec, sin2psi, cos2psi;
  long ipix;
  quat_t q;
  
  for (int ii=0; ii<n; ii++) {
    qp_bore2det_hwp(mem, q_off, ctime[ii], q_bore[ii], q_hwp[ii], q);
    qp_quat2radec(mem, q, &ra, &dec, &sin2psi, &cos2psi);
    ipix = qp_radec2pix(mem, nside, ra, dec);
    pmap[ipix][0] += 2;
    pmap[ipix][3] += 2*cos2psi*cos2psi;
    pmap[ipix][4] += 2*cos2psi*sin2psi;
    pmap[ipix][5] += 2*sin2psi*sin2psi;
  }
}

/* Compute pointing matrix map for given boresight timestream and many detector
   offsets. pmap a 6-x-npix array containing (hits, p01, p02, p11, p12, p22).
   openMP-parallelized. */
void qp_bore2pnt(qp_memory_t *mem, quat_t *q_off, int ndet,
		 double *ctime, quat_t *q_bore, int n,
		 pixel_t *pmap, int nside) {
  
  long npix = nside2npix(nside);

#pragma omp parallel
  {
    
    // local map array
    pixel_t *pmaploc;
    if (mem->num_threads > 1) {
      pmaploc = calloc(npix,sizeof(pixel_t));
    } else {
      pmaploc = pmap;
    }
    
    // local copy of memory
    qp_memory_t memloc = *mem;
    
#pragma omp for nowait
    for (int idet=0; idet<ndet; idet++) {
#ifdef DEBUG
      printf("thread %d, det %d\n", omp_get_thread_num(), idet);
      printf("offset %f %f %f %f\n", q_off[idet][0], q_off[idet][1],
	     q_off[idet][2], q_off[idet][3]);
#endif
      if (mem->pair_dets)
	qp_bore2pnt_pair(&memloc, q_off[idet], ctime, q_bore, n, pmaploc, nside);
      else
	qp_bore2pnt_single(&memloc, q_off[idet], ctime, q_bore, n, pmaploc, nside);
    }
    
    if (mem->num_threads > 1) {
      // reduce
#pragma omp critical
      {
	for (int ipix=0; ipix<npix; ipix++)
	  for (int ii=0; ii<6; ii++)
	    pmap[ipix][ii] += pmaploc[ipix][ii];
      }
      
      free(pmaploc);
    }
  }
}

/* Compute signal map for given boresight timestream, many signal timestreams,
   and many detector offsets.
   smap is a npix-x-3 array containing (d, d*cos(2 psi), d*sin(2 psi)).
   openMP-parallelized. */
void qp_bore2sig(qp_memory_t *mem, quat_t *q_off, int ndet,
                 double *ctime, quat_t *q_bore, double **tod, int n,
                 vec3_t *smap, int nside) {

  long npix = nside2npix(nside);

#pragma omp parallel
  {

    // local map array
    vec3_t *smaploc;
    if (mem->num_threads > 1) {
      smaploc = calloc(npix, sizeof(vec3_t));
    } else {
      smaploc = smap;
    }

    // local copy of memory
    qp_memory_t memloc = *mem;

#pragma omp for nowait
    for (int idet=0; idet<ndet; idet++) {
      qp_bore2sig_single(&memloc, q_off[idet], ctime, q_bore, tod[idet], n,
                         smaploc, nside);
    }

    if (mem->num_threads > 1) {
      // reduce
#pragma omp critical
      {
        for (int ipix=0; ipix<npix; ipix++)
          for (int ii=0; ii<3; ii++)
            smap[ipix][ii] += smaploc[ipix][ii];
      }

      free(smaploc);
    }
  }
}

/* Compute signal and pointing matrix maps for given boresight timestream,
   many signal timestreams, and many detector offsets.
   smap is a npix-x-3 array containing (d, d*cos(2 psi), d*sin(2 psi)).
   pmap is a npix-x-6 array containing (hits, p01, p02, p11, p12, p22).
   openMP-parallelized. */
void qp_bore2sigpnt(qp_memory_t *mem, quat_t *q_off, int ndet,
                    double *ctime, quat_t *q_bore, double **tod, int n,
                    vec3_t *smap, pixel_t *pmap, int nside) {

  long npix = nside2npix(nside);

#pragma omp parallel
  {

    // local map array
    vec3_t *smaploc;
    pixel_t *pmaploc;
    if (mem->num_threads > 1) {
      smaploc = calloc(npix, sizeof(vec3_t));
      pmaploc = calloc(npix, sizeof(pixel_t));
    } else {
      smaploc = smap;
      pmaploc = pmap;
    }

    // local copy of memory
    qp_memory_t memloc = *mem;

#pragma omp for nowait
    for (int idet=0; idet<ndet; idet++) {
      qp_bore2sigpnt_single(&memloc, q_off[idet], ctime, q_bore, tod[idet], n,
                            smaploc, pmaploc, nside);
    }

    if (mem->num_threads > 1) {
      // reduce
#pragma omp critical
      {
        for (int ipix=0; ipix<npix; ipix++)
          for (int ii=0; ii<6; ii++) {
            if (ii<3)
              smap[ipix][ii] += smaploc[ipix][ii];
            pmap[ipix][ii] += pmaploc[ipix][ii];
          }
      }

      free(smaploc);
      free(pmaploc);
    }
  }
}

/* Compute pointing matrix map for given boresight timestream and many detector
   offsets. pmap a 6-x-npix array containing (hits, p01, p02, p11, p12, p22).
   openMP-parallelized. */
void qp_bore2pnt_hwp(qp_memory_t *mem, quat_t *q_off, int ndet,
		     double *ctime, quat_t *q_bore, quat_t *q_hwp, int n,
		     pixel_t *pmap, int nside) {
  
  long npix = nside2npix(nside);

#pragma omp parallel
  {
    
    // local map array
    pixel_t *pmaploc;
    if (mem->num_threads > 1) {
      pmaploc = calloc(npix,sizeof(pixel_t));
    } else {
      pmaploc = pmap;
    }
    
    // local copy of memory
    qp_memory_t memloc = *mem;
    
#pragma omp for nowait
    for (int idet=0; idet<ndet; idet++) {
#ifdef DEBUG
      printf("thread %d, det %d\n", omp_get_thread_num(), idet);
      printf("offset %f %f %f %f\n", q_off[idet][0], q_off[idet][1],
	     q_off[idet][2], q_off[idet][3]);
#endif
      if (mem->pair_dets)
	qp_bore2pnt_pair_hwp(&memloc, q_off[idet], ctime, q_bore, q_hwp, n,
			     pmaploc, nside);
      else
	qp_bore2pnt_single_hwp(&memloc, q_off[idet], ctime, q_bore, q_hwp, n,
			       pmaploc, nside);
    }
    
    if (mem->num_threads > 1) {
      // reduce
#pragma omp critical
      {
	for (int ipix=0; ipix<npix; ipix++)
	  for (int ii=0; ii<6; ii++)
	    pmap[ipix][ii] += pmaploc[ipix][ii];
      }
      
      free(pmaploc);
    }
  }
}

/* Compute signal map for given boresight timestream, hwp timestream,
   many signal timestreams, and many detector offsets.
   smap is a npix-x-3 array containing (d, d*cos(2 psi), d*sin(2 psi)).
   openMP-parallelized. */
void qp_bore2sig_hwp(qp_memory_t *mem, quat_t *q_off, int ndet,
                     double *ctime, quat_t *q_bore, quat_t *q_hwp,
                     double **tod, int n, vec3_t *smap, int nside) {

  long npix = nside2npix(nside);

#pragma omp parallel
  {

    // local map array
    vec3_t *smaploc;
    if (mem->num_threads > 1) {
      smaploc = calloc(npix, sizeof(vec3_t));
    } else {
      smaploc = smap;
    }

    // local copy of memory
    qp_memory_t memloc = *mem;

#pragma omp for nowait
    for (int idet=0; idet<ndet; idet++) {
      qp_bore2sig_single_hwp(&memloc, q_off[idet], ctime, q_bore, q_hwp,
                             tod[idet], n, smaploc, nside);
    }

    if (mem->num_threads > 1) {
      // reduce
#pragma omp critical
      {
        for (int ipix=0; ipix<npix; ipix++)
          for (int ii=0; ii<3; ii++)
            smap[ipix][ii] += smaploc[ipix][ii];
      }

      free(smaploc);
    }
  }
}

/* Compute signal and pointing matrix maps for given boresight timestream,
   hwp timestrea, many signal timestreams, and many detector offsets.
   smap is a npix-x-3 array containing (d, d*cos(2 psi), d*sin(2 psi)).
   pmap is a npix-x-6 array containing (hits, p01, p02, p11, p12, p22).
   openMP-parallelized. */
void qp_bore2sigpnt_hwp(qp_memory_t *mem, quat_t *q_off, int ndet,
                        double *ctime, quat_t *q_bore, quat_t *q_hwp,
                        double **tod, int n, vec3_t *smap, pixel_t *pmap,
                        int nside) {

  long npix = nside2npix(nside);

#pragma omp parallel
  {

    // local map array
    vec3_t *smaploc;
    pixel_t *pmaploc;
    if (mem->num_threads > 1) {
      smaploc = calloc(npix, sizeof(vec3_t));
      pmaploc = calloc(npix, sizeof(pixel_t));
    } else {
      smaploc = smap;
      pmaploc = pmap;
    }

    // local copy of memory
    qp_memory_t memloc = *mem;

#pragma omp for nowait
    for (int idet=0; idet<ndet; idet++) {
      qp_bore2sigpnt_single_hwp(&memloc, q_off[idet], ctime, q_bore, q_hwp,
                                tod[idet], n, smaploc, pmaploc, nside);
    }

    if (mem->num_threads > 1) {
      // reduce
#pragma omp critical
      {
        for (int ipix=0; ipix<npix; ipix++)
          for (int ii=0; ii<6; ii++) {
            if (ii<3)
              smap[ipix][ii] += smaploc[ipix][ii];
            pmap[ipix][ii] += pmaploc[ipix][ii];
          }
      }

      free(smaploc);
      free(pmaploc);
    }
  }
}

void qp_set_opt_num_threads(qp_memory_t *mem, int num_threads) {
  if (num_threads == 0) {
#ifdef _OPENMP
    num_threads = omp_get_num_procs();
#else
    num_threads = 1;
#endif
  }
  mem->num_threads = num_threads;
#ifdef _OPENMP
  omp_set_num_threads(num_threads);
#endif
}

int qp_get_opt_num_threads(qp_memory_t *mem) {
  return mem->num_threads;
}