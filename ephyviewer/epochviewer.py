# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, print_function, division, absolute_import)


import numpy as np

import matplotlib.cm
import matplotlib.colors

from .myqt import QT
import pyqtgraph as pg

from .base import BaseMultiChannelViewer, Base_ParamController



default_params = [
    {'name': 'xsize', 'type': 'float', 'value': 3., 'step': 0.1, 'limits':(0,np.inf)},
    {'name': 'background_color', 'type': 'color', 'value': 'k'},
    {'name': 'display_labels', 'type': 'bool', 'value': True},
    ]

default_by_channel_params = [ 
    {'name': 'color', 'type': 'color', 'value': "55FF00"},
    {'name': 'visible', 'type': 'bool', 'value': True},
    ]




class EpochViewer_ParamController(Base_ParamController):
    def __init__(self, parent=None, viewer=None):
        Base_ParamController.__init__(self, parent=parent, viewer=viewer)


        h = QT.QHBoxLayout()
        self.mainlayout.addLayout(h)
        
        self.v1 = QT.QVBoxLayout()
        h.addLayout(self.v1)
        self.tree_params = pg.parametertree.ParameterTree()
        self.tree_params.setParameters(self.viewer.params, showTop=True)
        self.tree_params.header().hide()
        self.v1.addWidget(self.tree_params)

        self.tree_by_channel_params = pg.parametertree.ParameterTree()
        self.tree_by_channel_params.header().hide()
        h.addWidget(self.tree_by_channel_params)
        self.tree_by_channel_params.setParameters(self.viewer.by_channel_params, showTop=True)        
        v = QT.QVBoxLayout()
        h.addLayout(v)
        
        
        if self.source.nb_channel>1:
            v.addWidget(QT.QLabel('<b>Select channel...</b>'))
            names = [p.name() for p in self.viewer.by_channel_params]
            self.qlist = QT.QListWidget()
            v.addWidget(self.qlist, 2)
            self.qlist.addItems(names)
            self.qlist.setSelectionMode(QT.QAbstractItemView.ExtendedSelection)
            
            for i in range(len(names)):
                self.qlist.item(i).setSelected(True)            
            v.addWidget(QT.QLabel('<b>and apply...<\b>'))
            
        
        
        but = QT.QPushButton('set visble')
        v.addWidget(but)
        but.clicked.connect(self.on_set_visible)
    
    @property
    def selected(self):
        selected = np.ones(self.viewer.source.nb_channel, dtype=bool)
        if self.viewer.source.nb_channel>1:
            selected[:] = False
            selected[[ind.row() for ind in self.qlist.selectedIndexes()]] = True
        return selected
    
    @property
    def visible_channels(self):
        visible = [self.viewer.by_channel_params['Channel{}'.format(i), 'visible'] for i in range(self.source.nb_channel)]
        return np.array(visible, dtype='bool')

    def on_set_visible(self):
        # apply
        visibles = self.selected
        for i,param in enumerate(self.viewer.by_channel_params.children()):
            param['visible'] = visibles[i]


class RectItem(pg.GraphicsWidget):
    def __init__(self, rect, border = 'r', fill = 'g'):
        pg.GraphicsWidget.__init__(self)
        self.rect = rect
        self.border= border
        self.fill= fill
    
    def boundingRect(self):
        return QT.QRectF(0, 0, self.rect[2], self.rect[3])
        
    def paint(self, p, *args):
        p.setPen(pg.mkPen(self.border))
        p.setBrush(pg.mkBrush(self.fill))
        p.drawRect(self.boundingRect())


class DataGrabber(QT.QObject):
    data_ready = QT.pyqtSignal(float, float, object, object)
    
    def __init__(self, source, parent=None):
        QT.QObject.__init__(self, parent)
        self.source = source
        
    def on_request_data(self, t_start, t_stop, visibles):
        data = {}
        for e, chan in enumerate(visibles):
            times, durations, labels = self.source.get_chunk_by_time(chan=chan,  t_start=t_start, t_stop=t_stop)
            data[chan] = (times, durations, labels)
        self.data_ready.emit(t_start, t_stop, visibles, data)
    

class EpochViewer(BaseMultiChannelViewer):
    _default_params = default_params
    _default_by_channel_params = default_by_channel_params
    
    _ControllerClass = EpochViewer_ParamController
    
    request_data = QT.pyqtSignal(float, float, object)
    
    def __init__(self, **kargs):
        BaseMultiChannelViewer.__init__(self, **kargs)
        
        self.initialize_plot()
        
        self._xratio = 0.3
        
        self.thread = QT.QThread(parent=self)
        self.datagrabber = DataGrabber(source=self.source)
        self.datagrabber.moveToThread(self.thread)
        self.thread.start()
        
        
        self.datagrabber.data_ready.connect(self.on_data_ready)
        self.request_data.connect(self.datagrabber.on_request_data)
        
    
    def initialize_plot(self):
        pass
    
    def refresh(self):
        xsize = self.params['xsize']
        t_start, t_stop = self.t-xsize*self._xratio , self.t+xsize*(1-self._xratio)
        visibles, = np.nonzero(self.params_controller.visible_channels)
        self.request_data.emit(t_start, t_stop, visibles)

    def on_data_ready(self, t_start, t_stop, visibles, data):
        self.plot.clear()
        self.graphicsview.setBackground(self.params['background_color'])
        
        for e, chan in enumerate(visibles):
            times, durations, labels = data[chan]
            
            color = self.by_channel_params.children()[e].param('color').value()
            color2 = QT.QColor(color)
            color2.setAlpha(130)
            
            ypos = visibles.size-e-1
            
            for i in range(times.size):
                item = RectItem([times[i],  ypos,durations[i], .9],  border = color, fill = color2)
                item.setPos(times[i],  visibles.size-e-1)
                self.plot.addItem(item)

            if self.params['display_labels']:
                label_name = '{}: {}'.format(chan, self.source.get_name(chan=chan))
                label = pg.TextItem(label_name, color=color, anchor=(0, 0.5), border=None, fill=pg.mkColor((128,128,128, 180)))
                self.plot.addItem(label)
                label.setPos(t_start, ypos+0.45)
        
        self.vline = pg.InfiniteLine(angle = 90, movable = False, pen = '#00FF00')
        self.plot.addItem(self.vline)

        self.vline.setPos(self.t)
        self.plot.setXRange( t_start, t_stop)
        self.plot.setYRange( 0, visibles.size)

