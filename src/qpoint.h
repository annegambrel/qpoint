#pragma once

#ifdef __cplusplus
extern "C" {
#endif

  /* Quaternion */
  typedef double quat_t[4];
  
  /* 3-vector */
  typedef double vec3_t[3];
  
  /* ************************************************************************* 
     Internal parameter settings
     ********************************************************************** */
  
  /* state structure for keeping track of transformation updates */
  typedef struct {
    double update_rate; // period in seconds
    double ctime_last; // time of last update
  } qp_state_t;
  
  /* structure for storing refraction data */
  typedef struct {
    double height;      // height, m
    double temperature; // temperature, C
    double pressure;    // pressure, mbar
    double humidity;    // humidity, fraction
    double frequency;   // frequency, ghz
    double lapse_rate;  // tropospheric lapse rate, K/m
  } qp_weather_t;
  
  /* structures for storing Bulletin A data (for wobble correction) */
  typedef struct {
    float x;
    float y;
    float dut1;
  } qp_bulletina_entry_t;
  
  typedef struct {
    qp_bulletina_entry_t *entries;
    int mjd_min;
    int mjd_max;
  } qp_bulletina_t;
  
  /* parameter structure for storing corrections computed at variable rates */
  typedef struct qp_memory_t {
    int initialized;
    
    // update state
    qp_state_t state_daber;     // diurnal aberration
    qp_state_t state_lonlat;    // lat/lon
    qp_state_t state_wobble;    // polar motion
    qp_state_t state_dut1;      // ut1 correction
    qp_state_t state_erot;      // earth's rotation
    qp_state_t state_npb;       // nutation, precession, frame bias    
    qp_state_t state_aaber;     // annual aberration
    qp_state_t state_ref;       // refraction
    
    // state data
    qp_weather_t weather;     // weather
    double ref_tol;           // refraction tolerance, rad
    double ref_delta;         // refraction correction, deg
    double dut1;              // UT1 correction
    quat_t q_lonlat;          // lonlat quaternion
    quat_t q_wobble;          // wobble quaternion
    quat_t q_npb;             // nutation etc quaternion
    quat_t q_erot;            // earth's rotation quaternion
    vec3_t beta_earth;        // earth velocity
    qp_bulletina_t bulletinA; // bulletin A data
    
    // options
    int accuracy;          // 0=full accuracy, 1=low accuracy
    int mean_aber;         // 0=per-detector aberration, 1=mean
    int fast_math;         // 0=regular trig, 1=polynomial trig approximations
    int polconv;           // polarization convention (0=healpix,1=IAU)
    int pair_dets;         // pair A/B detectors for bore2map (1=True, 0=False)
    int pix_order;         // pixel ordering (1=nest, 0=ring)
    int num_threads;       // number of parallel threads
  } qp_memory_t;
  
  /* parameter initialization */
  qp_memory_t * qp_init_memory(void);
  void qp_free_memory(qp_memory_t *mem);
  
  /* common update rates */
#define QP_DO_ALWAYS 0
#define QP_DO_ONCE   -1
#define QP_DO_NEVER  -999
  
  /* Set correction rates for each state, in seconds; control accuracy and speed
     Use above macros to allow states to be applied always, once or never. */
  void qp_set_rates(qp_memory_t *mem,
		    double daber_rate,
		    double lonlat_rate,
		    double wobble_rate,
		    double dut1_rate,
		    double erot_rate,
		    double npb_rate,
		    double aaber_rate,
		    double ref_rate);
  
  /* reset counters so that all corrections are recalculated at next sample */
  void qp_reset_rates(qp_memory_t *mem);
  
  /* Check whether a correction needs to be updated */
  int qp_check_update(qp_state_t *state, double ctime);
  
  /* check whether a correction needs to be applied */
  int qp_check_apply(qp_state_t *state);
  
  /* print quaternion to screen */
  void qp_print_debug(const char *tag, quat_t q);
  
  /* per-correction functions */
#define RATEFUNC(state)					  \
  void qp_set_rate_##state(qp_memory_t *mem, double rate); \
  void qp_reset_rate_##state(qp_memory_t *mem);		  \
  double qp_get_rate_##state(qp_memory_t *mem);
  RATEFUNC(daber)
  RATEFUNC(lonlat)
  RATEFUNC(wobble)
  RATEFUNC(dut1)
  RATEFUNC(erot)
  RATEFUNC(npb)
  RATEFUNC(aaber)
  RATEFUNC(ref)
  
  /* per-option functions */
  void qp_set_options(qp_memory_t *mem,
		      int accuracy,
		      int mean_aber,
		      int fast_math,
		      int polconv,
		      int pair_dets,
		      int pix_order,
		      int num_threads);

#define OPTIONFUNC(opt)				    \
  void qp_set_opt_##opt(qp_memory_t *mem, int val); \
  int qp_get_opt_##opt(qp_memory_t *mem);
  OPTIONFUNC(accuracy);
  OPTIONFUNC(mean_aber);
  OPTIONFUNC(fast_math);
  OPTIONFUNC(polconv);
  OPTIONFUNC(pair_dets);
  OPTIONFUNC(pix_order);
  OPTIONFUNC(num_threads);
  
  /* Set weather data */
  void qp_set_weather(qp_memory_t *mem,
		      double height, double temperature, double pressure,
		      double humidity, double frequency, double lapse_rate);
  
#define WEATHFUNC(param)				     \
  void qp_set_weather_##param(qp_memory_t *mem, double val); \
  double qp_get_weather_##param(qp_memory_t *mem);
  WEATHFUNC(height)
  WEATHFUNC(temperature)
  WEATHFUNC(pressure)
  WEATHFUNC(humidity)
  WEATHFUNC(frequency)
  WEATHFUNC(lapse_rate)

#define DOUBLEFUNC(param)				 \
  void qp_set_##param(qp_memory_t *mem, double val); \
  double qp_get_##param(qp_memory_t *mem);
  DOUBLEFUNC(ref_tol)
  DOUBLEFUNC(ref_delta)
  DOUBLEFUNC(dut1)

  /* ************************************************************************* 
     Utility functions
     ********************************************************************** */
  
  /* diurnal aberration constant (radians) */
#define D_ABER_RAD 1.430408829156e-06 // -0.295043 arcsec
  /* speed of light, AU/day */
#define C_AUD 173.14463269999999 
  /* speed of light, m/s */
#define C_MS 299792458.0

  /* Return interpolated values from IERS Bulletin A */
  int get_iers_bulletin_a( qp_memory_t *mem, double mjd,
			   double *dut1, double *x, double *y );
  /* Set IERS Bulletin A */
  int set_iers_bulletin_a( qp_memory_t *mem, int mjd_min_, int mjd_max_,
			   double *dut1, double *x, double *y );
  
  /* Time conversion */
#define CTIME_JD_EPOCH 2440587.5 /* JD for ctime = 0 */
  void ctime2jd(double ctime, double jd[2]);
  double jd2ctime(double jd[2]);
  void ctime2jdtt(double ctime, double jd_tt[2]);
  void jdutc2jdut1(double jd_utc[2], double dut1, double jd_ut1[2]);
  double ctime2gmst(double ctime, double dut1, int accuracy);
  static inline double secs2days( double s ) { return s/86400.; }
  static inline double days2secs( double d ) { return d*86400.; }
  static inline double jd2mjd( double jd ) { return jd - 2400000.5; }
  static inline double mjd2jd( double mjd ) { return mjd + 2400000.5; }
  
  /* Unit conversions */
#ifndef M_PI
#define M_PI		3.14159265358979323846	// pi
#define M_PI_2		1.57079632679489661923	// pi/2
#endif
  static const double d2r = M_PI/180.;
  static const double r2d = 180./M_PI;
  static inline double deg2rad( double deg ) { return deg*d2r; }
  static inline double rad2deg( double rad ) { return rad*r2d; }
  static const double as2r = M_PI/(180.*3600.);
  static const double r2as = 3600.*180./M_PI;
  static inline double arcsec2rad( double sec ) { return sec*as2r; }
  static inline double rad2arcsec( double rad ) { return rad*r2as; }
  
  /* ************************************************************************* 
     Intermediate rotations and corrections
     ********************************************************************** */
  
  /* Calculate aberration correction quaternion
     v = (R(q)*z) x beta, angle = |v|, qa = quat(-angle,v) */
  void qp_aberration(quat_t q, vec3_t beta, quat_t qa);
  
  /* Calculate earth orbital velocity vector as fraction of speed of light */
  void qp_earth_orbital_beta(double jd_tdb[2], vec3_t beta);
  
  /* Apply annual aberration correction to given quaternion */
  void qp_apply_annual_aberration(qp_memory_t *mem, double ctime, quat_t q);
  
  /* Calculate nutation/precession/bias correction quaternion
     use (faster) truncated series if accuracy > 0*/
  void qp_npb_quat(double jd_tt[2], quat_t q, int accuracy);
  
  /* Calculate ERA quaternion */
  void qp_erot_quat(double jd_ut1[2], quat_t q);
  
  /* Calcuate wobble correction quaternion */
  void qp_wobble_quat(double xy, double yp, quat_t q);
  
  /* Calculate gondola orientation quaternion */
  void qp_azel_quat(double az, double el, double pitch, double roll, quat_t q);
  
  /* Calculate longitude/latitude quaternion */
  void qp_lonlat_quat(double lon, double lat, quat_t q);
  
  /* Calculate local mean sidereal time */
  double qp_lmst(qp_memory_t *mem, double ctime, double lon);
  
  /* Calculate local mean sidereal time */
  void qp_lmstn(qp_memory_t *mem, double *ctime, double *lon, double *lmst,
		int n);
  
  /* Calculate waveplate quaternion, given _physical_ HWP angle */
  void qp_hwp_quat(double ang, quat_t q);
  
  /* Calculate waveplate quaternions */
  void qp_hwp_quatn(double *ang, quat_t *q, int n);
  
  /* Calculate atmospheric refraction */
  double qp_refraction(double el, double lat, double height, double temp,
		       double press, double hum, double freq, double lapse,
		       double tol);
  
  /* Update atmospheric refraction using stored parameters */
  double qp_update_ref(qp_memory_t *mem, double el, double lat);
  
  /* ************************************************************************* 
     Output functions
     ********************************************************************** */
  
  /* Compute boresight quaternion for a single gondola orientation. */
  void qp_azel2quat(qp_memory_t *mem, double az, double el, double pitch,
		    double roll, double lon, double lat, double ctime,
		    quat_t q);
  
  /* Compute boresight quaternions for n gondola orientations. */
  void qp_azel2bore(qp_memory_t *mem, double *az, double *el, double *pitch,
		    double *roll, double *lon, double *lat, double *ctime,
		    quat_t *q, int n);
  
  /* Compute detector offset quaternion. */
  void qp_det_offset(double delta_az, double delta_el, double delta_psi,
		     quat_t q);

  
  /* Compute detector offset quaternion. */
  void qp_det_offsetn(double *delta_az, double *delta_el, double *delta_psi,
		      quat_t *q, int n);
  
  /* Compute ra/dec and sin(2*psi)/cos(2*psi) for a given quaternion */
  void qp_quat2radec(qp_memory_t *mem, quat_t q, double *ra, double *dec,
		     double *sin2psi, double *cos2psi);
  
  /* Compute ra/sin(dec) and sin(2*psi)/cos(2*psi) for a given quaternion */
  void qp_quat2rasindec(qp_memory_t *mem, quat_t q, double *ra, double *sindec,
			double *sin2psi, double *cos2psi);
  
  /* Calculate the detector quaternion from the boresight and offset. */
  void qp_bore2det(qp_memory_t *mem, quat_t q_off, double ctime, quat_t q_bore,
		   quat_t q_det);
  
  /* Calculate the detector quaternion from the boresight, offset and HWP angle. */
  void qp_bore2det_hwp(qp_memory_t *mem, quat_t q_off, double ctime, quat_t q_bore,
		       quat_t q_hwp, quat_t q_det);
  
  /* Calculate ra/dec and sin(2*psi)/cos(2*psi) for a given detector offset,
     from an array of boresight quaternions. */
  void qp_bore2radec(qp_memory_t *mem, quat_t q_off, double *ctime, quat_t *q_bore,
		     double *ra, double *dec, double *sin2psi, double *cos2psi,
		     int n);
  
  /* Calculate ra/dec and sin(2*psi)/cos(2*psi) for a given detector offset,
     from an array of boresight and waveplate quaternions. */
  void qp_bore2radec_hwp(qp_memory_t *mem, quat_t q_off, double *ctime,
			 quat_t *q_bore, quat_t *q_hwp, double *ra, double *dec,
			 double *sin2psi, double *cos2psi, int n);
  
  /* Calculate ra/sin(dec) and sin(2*psi)/cos(2*psi) for a given detector offset. */
  void qp_bore2rasindec(qp_memory_t *mem, quat_t q_off, double *ctime, quat_t *q_bore,
			double *ra, double *sindec, double *sin2psi, double *cos2psi,
			int n);
  
  /* Calculate ra/sin(dec) and sin(2*psi)/cos(2*psi) for a given detector offset. */
  void qp_bore2rasindec_hwp(qp_memory_t *mem, quat_t q_off, double *ctime,
			    quat_t *q_bore, quat_t *q_hwp, double *ra, double *sindec,
			    double *sin2psi, double *cos2psi, int n);
  
  /* Calculate ra/dec and sin(2*psi)/cos(2*psi) for a given detector offset,
     from a set of boresight orientations. */
  void qp_azel2radec(qp_memory_t *mem,
		     double delta_az, double delta_el, double delta_psi,
		     double *az, double *el, double *pitch, double *roll,
		     double *lon, double *lat, double *ctime, 
		     double *ra, double *dec, double *sin2psi, double *cos2psi,
		     int n);

  /* Calculate ra/dec and sin(2*psi)/cos(2*psi) for a given detector offset,
     from a set of boresight orientations and waveplate angles. */
  void qp_azel2radec_hwp(qp_memory_t *mem,
			 double delta_az, double delta_el, double delta_psi,
			 double *az, double *el, double *pitch, double *roll,
			 double *lon, double *lat, double *ctime, double *hwp,
			 double *ra, double *dec, double *sin2psi, double *cos2psi,
			 int n);
  
  /* Calculate ra/sin(dec) and sin(2*psi)/cos(2*psi) for a given detector offset,
     from a set of boresight orientations.  */
  void qp_azel2rasindec(qp_memory_t *mem,
			double delta_az, double delta_el, double delta_psi,
			double *az, double *el, double *pitch, double *roll,
			double *lon, double *lat, double *ctime, 
			double *ra, double *sindec, double *sin2psi, double *cos2psi,
			int n);

  /* Calculate ra/sin(dec) and sin(2*psi)/cos(2*psi) for a given detector offset,
     from a set of boresight orientations.  */
  void qp_azel2rasindec_hwp(qp_memory_t *mem,
			    double delta_az, double delta_el, double delta_psi,
			    double *az, double *el, double *pitch, double *roll,
			    double *lon, double *lat, double *ctime, double *hwp,
			    double *ra, double *sindec, double *sin2psi,
			    double *cos2psi, int n);
  
  /* ************************************************************************* 
     Pixelization
     ********************************************************************** */
  
  /* Pixel, contains (hits, p01, p02, p11, p12, p22) */
  typedef double pixel_t[6];
  
  /* Ordering */
  #define QP_ORDER_NEST 1
  #define QP_ORDER_RING 0
  
  /* Compute healpix pixel number for given nside and ra/dec */
  long qp_radec2pix(qp_memory_t *mem, double nside, double ra, double dec);
  
  /* Compute pointing matrix map for given boresight timestream and detector
     offset. pmap is a npix-x-6 array containing (hits, p01, p02, p11, p12, p22) */
  void qp_bore2map_single(qp_memory_t *mem, quat_t q_off,
			  double *ctime, quat_t *q_bore, int n,
			  pixel_t *pmap, int nside);
  
  /* Compute pointing matrix map for given boresight timestream and detector
     offset. pmap is a npix-x-6 array containing (hits, p01, p02, p11, p12, p22) */
  void qp_bore2map_single_hwp(qp_memory_t *mem, quat_t q_off,
			      double *ctime, quat_t *q_bore, quat_t *q_hwp, int n,
			      pixel_t *pmap, int nside);
  
  /* Compute pointing matrix map for given boresight timestream and detector
     offset for both A and B polarizations.
     pmap is a npix-x-6 array containing (hits, p01, p02, p11, p12, p22) */
  void qp_bore2map_pair(qp_memory_t *mem, quat_t q_off,
			double *ctime, quat_t *q_bore, int n,
			pixel_t *pmap, int nside);
  
  /* Compute pointing matrix map for given boresight timestream and detector
     offset for both A and B polarizations.
     pmap is a npix-x-6 array containing (hits, p01, p02, p11, p12, p22) */
  void qp_bore2map_pair_hwp(qp_memory_t *mem, quat_t q_off,
			    double *ctime, quat_t *q_bore, quat_t *q_hwp, int n,
			    pixel_t *pmap, int nside);
  
  /* Compute pointing matrix map for given boresight timestream and many detector
     offsets. pmap is a npix-x-6 array containing (hits, p01, p02, p11, p12, p22) */
  void qp_bore2map(qp_memory_t *mem, quat_t *q_off, int ndet,
		   double *ctime, quat_t *q_bore, int n,
		   pixel_t *pmap, int nside);
  
  /* Compute pointing matrix map for given boresight timestream and many detector
     offsets. pmap is a npix-x-6 array containing (hits, p01, p02, p11, p12, p22) */
  void qp_bore2map_hwp(qp_memory_t *mem, quat_t *q_off, int ndet,
		       double *ctime, quat_t *q_bore, quat_t *q_hwp, int n,
		       pixel_t *pmap, int nside);
  
#ifdef __cplusplus
}
#endif
