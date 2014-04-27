#!/usr/bin/python
"""
    Usage: 
        animSnapshots.py [options]
       
    Options:
        -h --help           Show this screen 
        -p --parallel       Case is decomposed
        -a --all            Process all times, otherwise last time step only
        -i --interpolate    Write images with interpolated fields
        --nlatest=num       Process only n latest time steps
        --slice=dir         Slice normal, default=y
        --config=file       Specify config file
        --gif               Create gifs
        --clean             Remove existing anim folder
        --update            Write till latest previously written snapshot
"""

import json
from paraview.simple import *
from paraview import servermanager
import os, sys
import numpy as np
from docopt import docopt
import subprocess
import shutil
from copy import deepcopy
#os.environ['DISPLAY'] = ":0"

def make_color_map(servermanager):
    color_map = servermanager.rendering.ScalarBarWidgetRepresentation()
    color_map.LabelColor = [0, 0, 0]
    color_map.TitleColor = [0, 0, 0]
    color_map.LabelFontSize = 12
    color_map.TitleFontSize = 12
    color_map.TitleBold = 1
    color_map.AspectRatio = 15
    color_map.Position = [0.8, 0.25]
    #color_map.Orientation ='Horizontal'
    return color_map


def camera_offset(alpha, bds):
    delta_z = abs(bds[4] - bds[5])
    delta_y = abs(bds[3] - bds[2])
    delta_x = abs(bds[1] - bds[0])
    g = (lambda delta: np.arctan(alpha * 90/3.1415) * delta)
    offs = 1.5*max(g(delta_x), g(delta_z), g(delta_y))
    return offs


def center_camera(bds):
    h = (lambda x, y: 0.5*(x+y))
    x = h(bds[1], bds[0])
    y = h(bds[3], bds[2])
    z = h(bds[5], bds[4])
    return [x, y, z]


def set_up_time_annotator():
    #annTime = AnnotateTimeFilter(reader)           # Time annotator
    #annTimeRepr = GetDisplayProperties(annTime)
    #annTimeRepr.Color=[0,0,0]                      # make time color black
    pass


def attachToDict(dict_, str_):
    d = dict_.keys()
    for k in d:
        if k+str_ not in d: dict_.update({k + str_: dict_[k]})


def field_names(reader):
    "return cell data field names, does not include lagrangian names"
    fields = reader.CellData.items()
    return [f[0] for f in fields]

def convert_to_gif(fields):
    for field in fields:
        try:
            com = "convert anim/{}_* anim/{}.gif > /dev/null 2>&1".format(
                                                                 field,
                                                                 field)
            out = subprocess.check_output(com, shell=True)
        except:
            pass

class animator():
    """  wrapper class to handle python-paraview
    """

    def __init__(self, 
             animate=False,
             decomposed=False,
             config=False,
             interpolate=False,
             update=False,
             cam_shift=1,
             cam_view_up=2,
             slice_normal=[0, -1, 0],
             ntimes=1,
            ):

        self.slice_normal = slice_normal
        self.cam_shift = cam_shift
        self.cam_view_up = cam_view_up
        self.anim = animate
        self.decomp = decomposed
        self.conf = self.read_config(config)
        self.path = os.getcwd()
        self.scalars = self.conf['scalars']
        self.vectors = self.conf['vectors']
        self.ntimes = ntimes
        self.interpolate = interpolate
        self.autoscaled = {}
        attachToDict(self.scalars, "Mean")
        #attachToDict(self.vectors, "Mean")
        # attachToDict(self.vectors, "Prime2Mean")
        Connect()
        self.create_reader()
        self.stop  =False
        self.setup_view()
        self.reprSlice = self.slice_domain()
        self.color_map = self.create_colormap()
        self.setup_camera()
        self.set_times()

    def read_config(self, fn):
        "read config file from script loc if no fn is given"
        fn = (fn if fn else os.path.dirname(os.path.realpath(__file__)) + '/readfiles.cfg')
        return json.load(open(fn))

    def make_anim_fold(self):
        try:
            os.makedirs(fullName + '/anim')
        except OSError:
            pass

    def create_reader(self):
        cdict = self.path + '/system/controlDict.foam'
        print "reading case data",
        self.reader = OpenDataFile(cdict)

        caseType = ('Decomposed Case' if self.decomp else 'Reconstructed Case')
        self.reader.CaseType = caseType
        self.has_changed() 
        print "\t[done]"

    def has_changed(self):
        self.reader.FileNameChanged()

    def set_times(self):
        "read all or latest ts from reader"
        times = self.reader.TimestepValues
        self.total_times = len(times)
        self.times = (times[::-1][:self.ntimes] if not self.anim else times[::-1])

    def setup_view(self, image_size=[780, 780]):
       self.view = CreateRenderView()
       self.view.StillRender = 1
       self.view.Background = [1, 1, 1]       # make background white
       self.view.CenterAxesVisibility = 0     # hide the center axis
       self.view.ViewSize = image_size

    def create_colormap(self):
        color_map = make_color_map(servermanager)
        self.view.Representations.append(color_map)
        return color_map

    def slice_domain(self):
        slice = Slice(self.reader)              # make a slice
        slice.SliceType.Normal = self.slice_normal   # set the slice normal
        Show(slice)                             # show the slice, needed -> yes
        #reprSlice.Representation = 'Outline'
        reprSlice = servermanager.CreateRepresentation(slice, self.view)
        reprSlice.Representation = 'Surface'
        return reprSlice

    def setup_camera(self):
        self.cam = self.view.GetActiveCamera()
        self.view.ResetCamera()
        bound_box = self.reader.GetDataInformation().GetBounds()
        cam_pos = center_camera(bound_box)
        self.view.CameraFocalPoint = cam_pos
        cam_pos[self.cam_shift] += camera_offset(self.cam.GetViewAngle(), bound_box)
        self.view.CameraPosition = cam_pos
        self.view.CameraViewUp = [0, 0, 0]
        self.view.CameraViewUp[self.cam_view_up] = 1
        self.view.OrientationAxesVisibility = 0
        #camera_position=camera.GetPosition()
        #camera_focal_point=camera.GetFocalPoint()


    def write_all_fields(self):
        for time_nr, t in enumerate(self.times):
            self.view.ViewTime = t
            self.frame_nr = self.total_times - time_nr
            print t
            self.has_changed()
            vectors = deepcopy(self.vectors)
            for field, limits in vectors.iteritems():
                try:
                    self.display_vector_field(field, limits)
                except:
                    pass
            scalars = deepcopy(self.scalars)
            for field, limits in scalars.iteritems():
                try:
                    self.display_scalar(field, limits)
                except:
                    pass
            if self.stop:
                print "STOP"
                break

    def display_vector_field(self, name, lim):
        ncomps = (3 if lim =="auto" else len(lim))
        for j in range(ncomps):
            self.set_field(name)
            lut = servermanager.rendering.PVLookupTable()
            lut.VectorMode = "Component" # Magnitude
            lut.VectorComponent = j
            if lim == 'auto':
               idx = self.reader.CellData.keys().index(name)
               arr = self.reader.CellData[idx]
               lim = arr.GetRange()
               self.vectors[name] = [lim, lim, lim]
            elif self.vectors.get(name, False):
                lim = self.vectors[name][j]
            lut.RGBPoints = [
                lim[0], 0.0, 0.0, 1.0,
                lim[1], 1.0, 0.0, 0.0,
                ]
            lut.ColorSpace = 'HSV'
            self.reprSlice.LookupTable = lut
            self.color_map.LookupTable = lut
            self.write_image(name, j)

    def display_scalar(self, name, lim):
        self.set_field(name)
        if lim == 'auto': 
           idx = self.reader.CellData.keys().index(name)
           arr = self.reader.CellData[idx]
           lim = arr.GetRange()
           self.scalars[name] = lim
        elif self.scalars.get(name, False):
            lim = self.scalars[name]
        self.reprSlice.LookupTable = MakeBlueToRedLT(lim[0], lim[1])
        self.color_map.LookupTable = MakeBlueToRedLT(lim[0], lim[1])
        self.write_image(name)

    def set_field(self, name):
        #reprSlice.MeshVisibility = 1
        self.reprSlice.ColorArrayName = str(name)
        _ = ('POINT_DATA' if self.interpolate else 'CELL_DATA')
        self.reprSlice.ColorAttributeType = _
        self.color_map.Title = str(name)

    def write_image(self, name, component=0):
        image_name = "{}/anim/{}_{}_{}_({}).png".format(self.path, name,
                                         component,
                                         str(self.frame_nr).zfill(4),
                                         self.view.ViewTime,
                                         )
        if os.path.exists(image_name) and self.update:
            print 'STOP'
            self.stop = True
            return 0
            
        WriteImage(image_name)
        print "written : " + image_name.split('/')[-1]

if __name__ == '__main__':

    arguments = docopt(__doc__)
    if arguments['--clean']: shutil.rmtree('anim')
    if not os.path.exists('anim'): os.makedirs('anim')
    config = arguments['--config']
    decomposed = (True if arguments['--parallel'] else False)
    animate = (True if arguments['--all'] else False)
    interpolate = (True if arguments['--interpolate'] else False)
    update = (True if arguments['--update'] else False)
    #fetch_fields = (False if arguments['--all-fields'] else True)
    cam_shift = cam_view_up = slice_normal = False
    ntimes = (int(arguments['--nlatest']) if arguments['--nlatest'] else 1)

    if arguments['--nlatest'] and arguments['--all']:
        print "cannot use --nlatest and --all at the same time"
        # exit 0

    if not arguments['--slice']:
        cam_shift = 1
        cam_view_up = 2
        slice_normal = [0, 1, 0]
    elif arguments['--slice'] == 'z':
        cam_shift = 2
        cam_view_up = 1
        slice_normal = [0, 0, 1]

    anim  = animator(animate, decomposed, config,
                     interpolate,
                     update,
                     cam_shift,
                     cam_view_up,
                     slice_normal,
                     ntimes
                    )
    anim.write_all_fields()
    
    if arguments['--gif']:
        convert_to_gif(anim.scalars)
        convert_to_gif(anim.vectors)
