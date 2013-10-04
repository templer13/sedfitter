from __future__ import print_function, division

import numpy as np
np.seterr(all='ignore')

from scipy.interpolate import interp1d

from astropy.logger import log
from astropy import units as u
from astropy.utils.misc import isiterable

from ..utils.validator import validate_scalar, validate_array

# TODO: get rid of use of interp1d


def is_numpy_array(variable):
    return issubclass(variable.__class__, (np.ndarray,
                                           np.core.records.recarray,
                                           np.ma.core.MaskedArray))


class ConvolvedFluxes(object):

    def __init__(self, wavelength=None, model_names=None, apertures=None,
                 flux=None, error=None,
                 initialize_arrays=False, initialize_units=u.mJy):

        self.model_names = model_names
        self.apertures = apertures
        self.wavelength = wavelength

        if initialize_arrays:

            if model_names is None:
                raise ValueError("model_names is required when using initialize_arrays=True")

            if apertures is None:
                raise ValueError("apertures is required when using initialize_arrays=True")

            if flux is None:
                self.flux = np.zeros((self.n_models, self.n_ap)) * initialize_units
            else:
                self.flux = flux

            if error is None:
                self.error = np.zeros((self.n_models, self.n_ap)) * initialize_units
            else:
                self.error = error

        else:

            self.flux = flux
            self.error = error

    @property
    def wavelength(self):
        """
        The central or characteristic wavelength of the filter
        """
        return self._wavelength

    @wavelength.setter
    def wavelength(self, value):
        if value is None:
            self._wavelength = None
        else:
            if isinstance(value, u.Quantity) and value.unit.is_equivalent(u.m):
                if not value.isscalar:
                    raise TypeError("wavelength should be a scalar Quantity")
                if not value > 0 * u.micron:
                    raise ValueError("wavelength should be strictly positive")
                self._wavelength = value
            else:
                raise TypeError("central wavelength should be given as a Quantity object with units of distance")

    @property
    def model_names(self):
        """
        The names of the models
        """
        return self._model_names

    @model_names.setter
    def model_names(self, value):
        if value is None:
            self._model_names = value
        else:
            self._model_names = validate_array('model_names', value, ndim=1)

    @property
    def apertures(self):
        """
        The apertures at which the SED is defined
        """
        return self._apertures

    @apertures.setter
    def apertures(self, value):
        if value is None:
            self._apertures = None
        else:
            if isinstance(value, u.Quantity) and value.unit.is_equivalent(u.m):
                self._apertures = validate_array('apertures', value, domain='positive', ndim=1)
            else:
                raise TypeError("apertures should be given as a Quantity object with units of length")

    @property
    def flux(self):
        """
        The SED fluxes
        """
        return self._flux

    @flux.setter
    def flux(self, value):
        if value is None:
            self._flux = value
        else:

            if self.model_names is None:
                raise ValueError("model_names has not been set")

            if isinstance(value, u.Quantity) and (value.unit.is_equivalent(u.erg/u.s) or value.unit.is_equivalent(u.erg/u.cm**2/u.s) or value.unit.is_equivalent(u.Jy)):
                self._flux = validate_array('flux', value, ndim=2, shape=(self.n_models, self.n_ap))
            else:
                raise TypeError("fluxes should be given as a Quantity object with units of luminosity, flux, or monochromatic flux density")

    @property
    def error(self):
        """
        The convolved flux errors
        """
        return self._error

    @error.setter
    def error(self, value):
        if value is None:
            self._error = value
        else:

            if self.model_names is None:
                raise ValueError("model_names has not been set")

            if isinstance(value, u.Quantity) and (value.unit.is_equivalent(u.erg/u.s) or value.unit.is_equivalent(u.erg/u.cm**2/u.s) or value.unit.is_equivalent(u.Jy)):
                self._error = validate_array('error', value, ndim=2, shape=(self.n_models, self.n_ap))
            else:
                raise TypeError("flux errors should be given as a Quantity object with units of luminosity, flux, or monochromatic flux density")

    @property
    def n_models(self):
        if self.model_names is None:
            return None
        else:
            return self.model_names.shape[0]

    @property
    def n_ap(self):
        if self.apertures is None:
            return 1
        else:
            return len(self.apertures)

    def __eq__(self, other):
        return self.wavelength == other.wavelength \
            and np.all(self.model_names == other.model_names) \
            and np.all(self.apertures == other.apertures) \
            and np.all(self.flux == other.flux) \
            and np.all(self.error == other.error)

    @classmethod
    def read(cls, filename):
        """
        Read convolved flux from a FITS file

        Parameters
        ----------
        filename : str
            The name of the FITS file to read the convolved fluxes from
        """

        from astropy.io import fits
        from astropy.table import Table

        conv = cls()

        # Open the convolved flux FITS file
        convolved = fits.open(filename)

        keywords = convolved[0].header

        # Try and read in the wavelength of the filter
        if 'FILTWAV' in keywords:
            conv.wavelength = keywords['FILTWAV'] * u.micron
        else:
            conv.wavelength = None

        # Read in apertures, if present
        try:
            ta = Table.read(convolved['APERTURES'])
            conv.apertures = ta['APERTURE'].data * ta['APERTURE'].unit
        except KeyError:
            pass

        # Create shortcuts to table
        tc = Table.read(convolved['CONVOLVED FLUXES'])

        # Read in model names
        conv.model_names = tc['MODEL_NAME']

        # Read in flux and flux errors

        if tc['TOTAL_FLUX'].ndim == 1 and conv.n_ap == 1:
            conv.flux = tc['TOTAL_FLUX'].data.reshape(tc['TOTAL_FLUX'].shape[0], 1) * tc['TOTAL_FLUX'].unit
        else:
            conv.flux = tc['TOTAL_FLUX'].data * tc['TOTAL_FLUX'].unit

        if tc['TOTAL_FLUX_ERR'].ndim == 1 and conv.n_ap == 1:
            conv.error = tc['TOTAL_FLUX_ERR'].data.reshape(tc['TOTAL_FLUX_ERR'].shape[0], 1) * tc['TOTAL_FLUX_ERR'].unit
        else:
            conv.error = tc['TOTAL_FLUX_ERR'].data * tc['TOTAL_FLUX_ERR'].unit

        # Read in 99% cumulative and 50% surface brightness radii
        try:
            conv.radius_sigma_50 = tc['RADIUS_SIGMA_50'] * tc['RADIUS_SIGMA_50'].unit
            conv.radius_cumul_99 = tc['RADIUS_CUMUL_99'] * tc['RADIUS_SIGMA_50'].unit
        except KeyError:
            pass

        return conv

    def write(self, filename, overwrite=False):
        """
        Write convolved flux to a FITS file.

        Parameters
        ----------
        filename: str
            The name of the file to output the convolved fluxes to.
        overwrite: bool, optional
            Whether to overwrite the output file
        """

        from astropy.io import fits
        from astropy.table import Table, Column

        tc = Table()
        tc['MODEL_NAME'] = self.model_names
        tc['TOTAL_FLUX'] = self.flux
        tc['TOTAL_FLUX_ERR'] = self.error

        if self.apertures is not None:
            radius_sigma_50 = self.find_radius_sigma(0.50)
            tc['RADIUS_SIGMA_50'] = radius_sigma_50
            radius_cumul_99 = self.find_radius_cumul(0.99)
            tc['RADIUS_CUMUL_99'] = radius_cumul_99

        if self.apertures is not None:
            ta = Table()
            ta['APERTURE'] = self.apertures

        # Primary HDU (for metadata)
        hdu0 = fits.PrimaryHDU()
        if self.wavelength is not None:
            hdu0.header['FILTWAV'] = self.wavelength.to(u.micron).value
        hdu0.header['NMODELS'] = self.n_models
        hdu0.header['NAP'] = self.n_ap

        # Convolved fluxes
        hdu1 = fits.BinTableHDU(np.array(tc), name='CONVOLVED FLUXES')
        hdu1.columns[1].unit = self.flux.unit.to_string(format='fits')
        hdu1.columns[2].unit = self.error.unit.to_string(format='fits')
        if self.apertures is not None:
            hdu1.columns[3].unit = radius_sigma_50.unit.to_string(format='fits')
            hdu1.columns[4].unit = radius_cumul_99.unit.to_string(format='fits')

        # Apertures
        if self.apertures is not None:
            hdu2 = fits.BinTableHDU(np.array(ta), name='APERTURES')
            hdu2.columns[0].unit = self.apertures.unit.to_string(format='fits')
        else:
            hdu2 = None

        hdulist = fits.HDUList([hdu0, hdu1] if hdu2 is None else [hdu0, hdu1, hdu2])
        hdulist.writeto(filename, clobber=overwrite)

    def interpolate(self, apertures):
        """
        Interpolate the flux to the apertures specified.

        Parameters
        ----------
        apertures : `astropy.units.Quantity` instance
            The apertures to interpolate to
        """

        # Initalize new ConvolvedFluxes object to return
        c = ConvolvedFluxes()

        # Set wavelength
        c.wavelength = self.wavelength

        # Save requested apertures
        c.apertures = apertures[:]

        # Transfer model names
        c.model_names = self.model_names

        # Interpolate to requested apertures
        if self.n_ap > 1:

            # If any apertures are larger than the defined max, reset to max
            if np.any(c.apertures > self.apertures.max()):
                apertures[c.apertures > self.apertures.max()] = self.apertures.max()

            # If any apertures are smaller than the defined min, raise error
            if np.any(c.apertures < self.apertures.min()):
                raise Exception("Aperture(s) requested too small")

            # Note that we have to be careful here because interp1d will drop
            # the units, so we need to make sure the new apertures are in the
            # same units as the current ones for the interpolation, and we need
            # to add the flux unit back.

            flux_interp = interp1d(self.apertures, self.flux)
            c.flux = flux_interp(c.apertures.to(self.apertures.unit)) * self.flux.unit

            # The following is not strictly correct - errors from interpolation is not interpolation of errors
            error_interp = interp1d(self.apertures, self.error)
            c.error = error_interp(c.apertures.to(self.apertures.unit)) * self.error.unit

        else:

            c.flux = np.repeat(self.flux, len(c.apertures)).reshape(c.n_models, len(c.apertures))
            c.error = np.repeat(self.error, len(c.apertures)).reshape(c.n_models, len(c.apertures))

        try:
            # TODO: is this actually correct?!
            c.radius_sigma_50 = self.radius_sigma_50[:]
            c.radius_cumul_99 = self.radius_cumul_99[:]
        except AttributeError:
            pass

        return c

    def find_radius_cumul(self, fraction):
        """
        Find for each model the radius containing a fraction of the flux.

        Parameters
        ----------
        fraction: float
            The fraction to use when determining the radius
        """

        log.info("Calculating radii containing %g%s of the flux" % (fraction * 100., '%'))

        radius = np.zeros(self.n_models, dtype=self.flux.dtype) * u.au

        if self.apertures is None:

            return radius

        else:

            required = fraction * self.flux[:, -1]

            # Linear interpolation - need to loop over apertures for vectorization
            for ia in range(len(self.apertures) - 1):
                calc = (required >= self.flux[:, ia]) & (required < self.flux[:, ia + 1])
                radius[calc] = (required[calc] - self.flux[calc, ia]) / \
                               (self.flux[calc, ia + 1] - self.flux[calc, ia]) * \
                               (self.apertures[ia + 1] - self.apertures[ia]) + \
                    self.apertures[ia]

            calc = (required < self.flux[:, 0])
            radius[calc] = self.apertures[0]

            calc = (required >= self.flux[:, -1])
            radius[calc] = self.apertures[-1]

            return radius

    def find_radius_sigma(self, fraction):
        """
        Find for each model a fractional surface brightness radius

        This is the outermost radius where the surface brightness is larger
        than a fraction of the peak surface brightness.

        Parameters
        ----------
        fraction: float
            The fraction to use when determining the radius
        """

        log.info("Calculating %g%s peak surface brightness radii" % (fraction * 100., '%'))

        sigma = np.zeros(self.flux.shape, dtype=self.flux.dtype)
        sigma[:, 0] = self.flux[:, 0] / self.apertures[0] ** 2
        sigma[:, 1:] = (self.flux[:, 1:] - self.flux[:, :-1]) / \
                       (self.apertures[1:] ** 2 - self.apertures[:-1] ** 2)

        maximum = np.max(sigma, axis=1)

        radius = np.zeros(self.n_models, dtype=self.flux.dtype) * u.au

        # Linear interpolation - need to loop over apertures backwards for vectorization
        for ia in range(len(self.apertures) - 2, -1, -1):
            calc = (sigma[:, ia] > fraction * maximum) & (radius == 0.)
            radius[calc] = (sigma[calc, ia] - fraction * maximum[calc]) / \
                           (sigma[calc, ia] - sigma[calc, ia + 1]) * \
                           (self.apertures[ia + 1] - self.apertures[ia]) + \
                self.apertures[ia]

        calc = sigma[:, -1] > fraction * maximum
        radius[calc] = self.apertures[-1]

        return radius
