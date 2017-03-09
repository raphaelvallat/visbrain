"""Convert user inputs and create Nd, 1d and Image objects.
"""
import numpy as np
from scipy.signal import spectrogram

from vispy import scene
import vispy.visuals.transforms as vist

from .marker import Markers
from ...utils import array2colormap, color2vb


__all__ = ["visuals"]


class visuals(object):
    """Create the visual objects to be added to the scene.

    This class create a Nd-plot, 1d-plot and Image-plot objects and set them
    parents on their own canvas.
    """

    def __init__(self, sf, data, time, channels, hypno, cameras=None,
                 method='agg', **kwargs):
        """Init."""
        # =================== CHANNELS ===================
        self._chan = ChannelPlot(channels, camera=cameras[0], method=method,
                                 color=self._chancolor, width=self._lw,
                                 color_detection=self._indicol,
                                 parent=self._chanCanvas)

        # =================== SPECTROGRAM ===================
        # Create a spectrogram object :
        self._spec = Spectrogram(camera=cameras[1],
                                 parent=self._specCanvas.wc.scene)
        self._spec.set_data(sf, data[0, ...], time)
        # Create a visual indicator for spectrogram :
        self._specInd = Indicator(name='spectro_indic', visible=True, alpha=.3,
                                  parent=self._specCanvas.wc.scene)
        self._specInd.set_data(xlim=(0, 30), ylim=(0, 20))

        # =================== HYPNOGRAM ===================
        # Create a hypnogram object :
        self._hyp = Hypnogram(time, camera=cameras[2], color=self._hypcolor,
                              width=self._lwhyp,
                              parent=self._hypCanvas.wc.scene)
        self._hyp.set_data(sf, hypno, time)
        # Create a visual indicator for hypnogram :
        self._hypInd = Indicator(name='hypno_indic', visible=True, alpha=.3,
                                 parent=self._hypCanvas.wc.scene)
        self._hypInd.set_data(xlim=(0., 30.), ylim=(-6., 2.))

        vbcanvas = self._chanCanvas + [self._specCanvas, self._hypCanvas]
        for k in vbcanvas:
            vbShortcuts.__init__(self, k.canvas)


"""
###############################################################################
# OBJECTS
###############################################################################
Classes below are used to create visual objects, display on sevral canvas :
- ChannelPlot : plot data (one signal per channel)
- Spectrogram : on a specific channel
- Hypnogram : sleep stages (can be optional)
"""


class ChannelPlot(object):
    """Plot each channel."""

    def __init__(self, channels, color=(.2, .2, .2), color_detection='red',
                 width=1.5, method='gl', camera=None, parent=None):
        # Variables :
        self._camera = camera
        self.rect = []
        self.width = width
        self.colidx = [np.array([])] * len(channels)

        # Get color :
        self.color = color2vb(color)
        self.color_detection = color2vb(color_detection)

        # Create one line pear channel :
        pos = np.zeros((1, 3), dtype=np.float32)
        self.mesh, self.report, self.grid, self.peak = [], [], [], []
        for i, k in enumerate(channels):
            # ----------------------------------------------
            # Create main line (for channel plot) :
            mesh = scene.visuals.Line(pos, name=k+'plot', color=self.color,
                                      method=method, parent=parent[i].wc.scene)
            self.mesh.append(mesh)
            # ----------------------------------------------
            # Create marker peaks :
            mesh = Markers(pos=np.zeros((1, 3), dtype=np.float32),
                           parent=parent[i].wc.scene)
            mesh.visible = False
            self.peak.append(mesh)
            # ----------------------------------------------
            # Report line :
            rep = scene.visuals.Line(pos, name=k+'report', method=method,
                                     color=self.color_detection,
                                     parent=parent[i].wc.scene)
            self.report.append(rep)
            # ----------------------------------------------
            # Create a grid :
            grid = scene.visuals.GridLines(color=(.1, .1, .1, .5),
                                           scale=(10., .1),
                                           parent=parent[i].wc.scene)
            grid.set_gl_state('translucent')
            self.grid.append(grid)

    def set_data(self, sf, data, time, sl=None, ylim=None):
        """Set data to channels.

        Args:
            data: np.ndarray
                Array of data of shape (n_channels, n_points)

            time: np.ndarray
                The time vector.

        Kargs:
            sl: slice, optional, (def: None)
                A slice object for the time selection of data.

            ylim: np.ndarray, optional, (def: None)
                Y-limits of each channel. Must be a (n_channels, 2) array.
        """
        if ylim is None:
            ylim = np.array([data.min(1), data.max(1)]).T

        # Manage slice :
        sl = slice(0, data.shape[1]) if sl is None else sl

        # Slice selection (of time and data) :
        timeSl = time[sl]
        self.x = (timeSl.min(), timeSl.max())
        dataSl = data[:, sl]
        z = np.full_like(timeSl, .5, dtype=np.float32)

        # Build a index vector:
        idx = np.arange(sl.start, sl.stop)

        # Set data to each plot :
        for i, k in enumerate(self.mesh):
            # Concatenate time / data / z axis :
            dat = np.vstack((timeSl, dataSl[i, :], z)).T
            # Indicator line :
            if self.colidx[i].size:
                # Find index that are both in idx and in indicator :
                inter = np.intersect1d(idx, self.colidx[i]) - sl.start
                # Build a array for connecting only consecutive segments :
                index = np.zeros((len(idx)), dtype=bool)
                index[inter] = True
                index[-1] = False
                # Send data to report :
                self.report[i].set_data(pos=dat, connect=index, width=4.,
                                        color=self.color_detection)
            # dat = np.ascontiguousarray(dat)
            k.set_data(dat, color=self.color, width=self.width)
            # Get camera rectangle and set it:
            rect = (self.x[0], ylim[i][0], self.x[1]-self.x[0],
                    ylim[i][1] - ylim[i][0])
            self._camera[i].rect = rect
            k.update()
            self.rect.append(rect)

    # ----------- PARENT -----------
    @property
    def parent(self):
        """Get the parent value."""
        return self.mesh[0].parent

    @parent.setter
    def parent(self, value):
        """Set parent value."""
        for i, k, in zip(value, self.mesh):
            k.parent = i.wc.scene


class Spectrogram(object):
    """Create and manage a Spectrogram object.

    After object creation, use the set_data() method to pass new data, new
    color, new frequency / time range, new settings...
    """

    def __init__(self, camera, parent=None):
        # Keep camera :
        self._camera = camera
        self._rect = (0., 0., 0., 0.)
        # Create a vispy image object :
        self.mesh = scene.visuals.Image(np.zeros((2, 2)), name='spectrogram',
                                        parent=parent)

    def set_data(self, sf, data, time, cmap='rainbow', nfft=30., overlap=0.5,
                 fstart=0.5, fend=20., contraste=.7):
        """Set data to the spectrogram.

        Use this method to change data, colormap, spectrogram settings, the
        starting and ending frequencies.

        Args:
            sf: float
                The sampling frequency.

            data: np.ndarray
                The data to use for the spectrogram. Must be a row vector.

            time: np.ndarray
                The time vector.

        Kargs:
            cmap: string, optional, (def: 'viridis')
                The matplotlib colormap to use.

            nfft: float, optional, (def: 256)
                Number of fft points for the spectrogram (in seconds).

            overlap: float, optional, (def: 0)
                Time overlap for the spectrogram (in seconds).

            fstart: float, optional, (def: None)
                Frequency from which the spectrogram have to start.

            fend: float, optional, (def: None)
                Frequency from which the spectrogram have to finish.

            contraste: float, optional, (def: .7)
                Contraste of the colormap.
        """
        # =================== CONVERSION ===================
        nperseg = int(round(nfft * sf))
        overlap = int(round(overlap * sf))

        # =================== COMPUTE ===================
        # Compute the spectrogram :
        freq, t, mesh = spectrogram(data, fs=sf, nperseg=nperseg,
                                    noverlap=overlap, window='hamming')
        mesh = 20 * np.log10(mesh)

        # =================== FREQUENCY SELECTION ===================
        # Find where freq is [fstart, fend] :
        f = [0., 0.]
        f[0] = np.abs(freq - fstart).argmin() if fstart else 0
        f[1] = np.abs(freq - fend).argmin() if fend else len(freq)
        # Build slicing and select frequency vector :
        sls = slice(f[0], f[1]+1)
        freq = freq[sls]
        self._fstart, self._fend = freq[0], freq[-1]

        # =================== COLOR ===================
        # Get clim :
        clim = (contraste * mesh.min(), contraste * mesh.max())
        # Turn mesh into color array for selected frequencies:
        self.mesh.set_data(array2colormap(mesh[sls, :], cmap=cmap,
                                          clim=clim))

        # =================== TRANSFORM ===================
        # Re-scale the mesh for fitting in time / frequency :
        fact = (freq.max()-freq.min())/len(freq)
        sc = (t.max()/mesh.shape[1], fact, 1)
        tr = [t[0], freq.min(), 0]
        self.mesh.transform = vist.STTransform(scale=sc, translate=tr)
        # Update object :
        self.mesh.update()
        # Get camera rectangle :
        self.rect = (time.min(), freq.min(), time.max()-time.min(),
                     freq.max()-freq.min())
        self.freq = freq

    # ----------- RECT -----------
    @property
    def rect(self):
        """Get the rect value."""
        return self._rect

    @rect.setter
    def rect(self, value):
        """Set rect value."""
        self._rect = value
        self._camera.rect = value


class Hypnogram(object):
    """Create a hypnogram object."""

    def __init__(self, time, camera, color='darkblue', width=2., parent=None):
        # Keep camera :
        self._camera = camera
        self._rect = (0., 0., 0., 0.)
        self.rect = (time.min(), -5., time.max() - time.min(), 7.)
        self.width = width
        # Get color :
        self.color = color2vb(color=color)
        # Create a default line :
        pos = np.array([[0, 0], [0, 100]])
        self.mesh = scene.visuals.Line(pos, name='hypnogram', color=self.color,
                                       method='gl', parent=parent)
        self.mesh.set_gl_state('translucent', depth_test=True)
        # Create a default marker (for edition):
        self.edit = Markers(parent=parent)
        # Create a reported marker (for detection):
        self.report = Markers(parent=parent)
        # self.mesh.set_gl_state('translucent', depth_test=True)
        self.mesh.set_gl_state('translucent', depth_test=False,
                               cull_face=True, blend=True, blend_func=(
                                          'src_alpha', 'one_minus_src_alpha'))
        # Add grid :
        self.grid = scene.visuals.GridLines(color=(.1, .1, .1, .5),
                                            scale=(10., 1.), parent=parent)
        self.grid.set_gl_state('translucent')

    def set_data(self, sf, data, time):
        """Set data to the hypnogram.

        Args:
            sf: float
                The sampling frequency.

            data: np.ndarray
                The data to send. Must be a row vector.

            time: np.ndarray
                The time vector
        """
        # Set data to the mesh :
        self.mesh.set_data(pos=np.vstack((time, -data)).T, width=self.width)
        self.mesh.update()

    def set_report(self, time, index, symbol='triangle_down', y=1., size=10.,
                   color='red'):
        """
        """
        # Get reduced version of time :
        timeSl = time[index]
        # Build y-position :
        y = np.full_like(timeSl, y) if isinstance(y, (int, float)) else y
        y += np.random.rand(len(y)) / 100.
        # Build data array :
        pos = np.vstack((timeSl, y)).T
        # Set data to report :
        self.report.set_data(pos=pos, face_color=color2vb(color, alpha=.9),
                             size=size, symbol=symbol, edge_width=0.)

    # ----------- RECT -----------
    @property
    def rect(self):
        """Get the rect value."""
        return self._rect

    @rect.setter
    def rect(self, value):
        """Set rect value."""
        self._rect = value
        self._camera.rect = value


"""
###############################################################################
# INDICATORS
###############################################################################
Visual indicators can be used to help the user to see in which time window the
signal is currently plotted. Those indicators are two vertical lines displayed
on the spectrogram and hypnogram.
"""


class Indicator(object):
    """Create a visual indicator (for spectrogram and hypnogram)."""

    def __init__(self, name='indicator', alpha=.3, visible=True, parent=None):
        # Create a vispy image object :
        image = color2vb('gray', alpha=alpha)[np.newaxis, ...]
        self.mesh = scene.visuals.Image(data=image, name=name,
                                        parent=parent)
        self.mesh.visible = visible

    def set_data(self, xlim, ylim):
        """Move the visual indicator.

        Args:
            xlim: tuple
                A tuple of two float indicating where xlim start and xlim end.

            ylim: tuple
                A tuple of two floats indicating where ylim start and ylim end.
        """
        tox = (xlim[0], ylim[0], -1.)
        sc = (xlim[1]-xlim[0], ylim[1]-ylim[0], 1.)
        # Move the square
        self.mesh.transform = vist.STTransform(translate=tox, scale=sc)


"""
###############################################################################
# SHORTCUTS
###############################################################################
Shortcuts applied on each canvas.
"""


class vbShortcuts(object):
    """This class add some shortcuts to the main canvas.

    It's also use to initialize to panel of shortcuts.

    Args:
        canvas: vispy canvas
            Vispy canvas to add the shortcuts.
    """

    def __init__(self, canvas):
        """Init."""
        # Add shortcuts to vbCanvas :
        @canvas.events.key_press.connect
        def on_key_press(event):
            """Executed function when a key is pressed on a keyboard over canvas.

            :event: the trigger event
            """
            if event.text == ' ':
                pass
            if event.text == 'n':  # Next (slider)
                self._SlWin.setValue(
                                self._SlWin.value() + self._SigSlStep.value())
            if event.text == 'b':  # Before (slider)
                self._SlWin.setValue(
                                self._SlWin.value() - self._SigSlStep.value())
            if event.text == '0':  # Toggle visibility on spec
                self._PanSpecViz.setChecked(not self._PanSpecViz.isChecked())
                self._fcn_specViz()
            if event.text == '1':  # Toggle visibility on hypno
                self._PanHypViz.setChecked(not self._PanHypViz.isChecked())
                self._fcn_hypViz()

        @canvas.events.mouse_release.connect
        def on_mouse_release(event):
            """Executed function when the mouse is pressed over canvas.

            :event: the trigger event
            """
            pass

        @canvas.events.mouse_double_click.connect
        def on_mouse_double_click(event):
            """Executed function when double click mouse over canvas.

            :event: the trigger event
            """
            pass

        @canvas.events.mouse_move.connect
        def on_mouse_move(event):
            """Executed function when the mouse move over canvas.

            :event: the trigger event
            """
            pass

        @canvas.events.mouse_press.connect
        def on_mouse_press(event):
            """Executed function when single click mouse over canvas.

            :event: the trigger event
            """
            # Display the rotation panel :
            pass
