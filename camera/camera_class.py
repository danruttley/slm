import os
import time
import numpy as np
import pandas as pd
import PIL.Image as PILImage
from shutil import copyfile

from .uc480 import uc480

class Camera():
    """Object which handles the taking and processing of images from the 
    ThorLabs DCC1545M-GL camera.
    """
    def __init__(self, exposure=1, blacklevel=0, gain=0, roi=None):
        self.exposure = exposure
        self.blacklevel = blacklevel
        self.gain = gain
        self.set_roi(roi)
        self.cam = uc480()
        self.cam.connect()

        self.update_exposure(self.exposure)
        self.update_blacklevel(self.blacklevel)
        self.update_gain(self.gain)
    
    def __del__(self):
        self.cam.disconnect()
    
    def update_exposure(self,exposure=None):
        """Sets and gets exposure time in ms."""
        if exposure != None:
            self.cam.set_exposure(exposure)
        self.exposure = self.cam.get_exposure()
        return self.exposure

    def update_blacklevel(self,blacklevel):
        """Set blacklevel compensation on or off."""
        self.blacklevel = blacklevel
        self.cam.set_blacklevel(self.blacklevel)
        return self.blacklevel
    
    def update_gain(self,gain=None):
        """Set and gets the gain level of the camera.
        
        Parameters:
            gain: gain of the camera. Between 0 - 100.
        """
        if gain != None:
            self.cam.set_gain(gain)
        self.gain = self.cam.get_gain()
        return self.gain

    def aquire(self):
        """Aquires a single array from the camera with the current settings."""
        array = self.cam.acquire() #acquire an image
        if self.roi != None:
            array = array[self.roi[1]:self.roi[3],self.roi[0]:self.roi[2]]
        if (array == 255).sum() > 0:
            print('Warning: image saturated')
        print(array)
        print(np.max(array))
        array[array > 255] = 255
        return np.uint8(array)

    def take_image(self):
        """Gets an image from the camera and returns it in an object containing
        the current camera settings.

        Returns:
            Image object containing the array from the camera and current 
            camera parameters.
        """
        array = self.aquire()
        return Image(array,self.exposure,self.blacklevel,self.roi)

    def set_roi(self,roi):
        """Sets the roi applied to images taken by the camera.

        Parameters:
            roi: None for no roi or [xmin,ymin,xmax,ymax]
        """
        self.roi = roi

class Image():
    """Custom image object containing the array as well as a dictionary 
    containing the camera settings when the image was taken. Custom properties 
    can be added, which will be saved when the image is saved.
    """
    def __init__(self,array=None,exposure=None,blacklevel=None,roi=None):
        self.array = array
        if roi == None:
            if not (array is None):
                xmin,ymin,xmax,ymax = [0,0,self.array.shape[1],self.array.shape[0]]
            else:
                xmin,ymin,xmax,ymax = None,None,None,None
        else:
            xmin,ymin,xmax,ymax = roi
        self.properties = {'exposure':exposure,
                           'blacklevel':blacklevel,
                           'roi_xmin':xmin,
                           'roi_ymin':ymin,
                           'roi_xmax':xmax,
                           'roi_ymax':ymax
                          }
        self.bgnd_array = None
        self.hologram = None
    
    def add_property(self,name,value):
        """Adds a property to the image properties dictonary."""
        self.properties[name] = value
    
    def get_properties(self):
        return self.properties
    
    def get_array(self):
        return self.array

    def add_background(self,bgnd_image):
        """Extracts an array from a background image"""
        if self.properties != bgnd_image.get_properties():
            print('Warning: background properties do not match image properties')
        self.bgnd_array = bgnd_image.get_array().copy()
    
    def get_background(self):
        return self.bgnd_array

    def add_hologram(self, hologram):
        self.hologram = hologram
    
    def get_hologram(self):
        return self.hologram

    def get_bgnd_corrected_array(self):
        return np.float32(self.array) - np.float32(self.bgnd_array)
    
    def get_pixel_count(self,correct_bgnd=True):
        if correct_bgnd:
            array = np.float32(self.array) - np.float32(self.bgnd_array)
        else:
            array = np.float32(self.array)
        sum = np.int(np.sum(array))
        return sum
    
    def get_max_pixel(self,correct_bgnd=True):
        if correct_bgnd:
            array = np.float32(self.array) - np.float32(self.bgnd_array)
        else:
            array = np.float32(self.array)
        return np.max(array)    

class ImageHandler():
    """Deals with the saving and loading of images from the ThorLabs camera"""
    def __init__(self,measure=None):
        """Creates the directory to save images in.

        Parameters:
            measure: the measure number to assign. -1 to append to the last 
                     measure, and None to create a new measure. If a string is
                     passed, this will be used as the subfolder name (without 
                     Measure prefixed)
        """
        self.created_dirs = False
        self.measure = measure

    def create_dirs(self,measure):
        date_dir = './images/'+time.strftime('%Y/%B/%d', time.localtime())
        os.makedirs(date_dir,exist_ok=True)

        if type(measure) == str:
            self.image_dir = date_dir+'/'+measure
        else:
            subfolders = [f.name for f in os.scandir(date_dir) if f.is_dir()]
            prev_measures = [f for f in subfolders if 'Measure' in f]
            prev_measures = [int(s.split('Measure ',1)[1]) for s in prev_measures]
            if prev_measures:
                if measure == -1:
                    measure = max(prev_measures)
                elif measure == None:
                    measure = max(prev_measures)+1
            else:
                measure = 0
            self.image_dir = date_dir+'/Measure {}'.format(measure)
        self.measure = measure
        print(self.image_dir)
        os.makedirs(self.image_dir,exist_ok=True)
        copyfile('main.py', self.image_dir+'/main.py')
        os.makedirs(self.image_dir+'/bgnds',exist_ok=True)
        os.makedirs(self.image_dir+'/holos',exist_ok=True)
        self.created_dirs = True
        try:
            self.df = pd.read_csv(self.image_dir+'/images.csv',index_col=0)
        except:
            self.df = pd.DataFrame()

    def show_image(self,image):
        plt.imshow(image, cmap='gray', vmin=0, vmax=255)
        plt.show()
    
    def save(self,image):
        """Save custom image object as a .png file and append the image 
        properties to the csv.
        """
        if not self.created_dirs:
            self.create_dirs(self.measure)
        array = image.get_array()
        properties = image.get_properties()
        print(properties)
        self.df = self.df.append(properties,ignore_index=True)
        filepath = self.image_dir+'/'+str(self.df.index[-1])+'.png'
        bgnd_filepath = self.image_dir+'/bgnds/'+str(self.df.index[-1])+'_bgnd.png'
        holo_filepath = self.image_dir+'/holos/'+str(self.df.index[-1])+'_holo.bmp'
        PILImage.fromarray(array,"L").save(filepath)
        self.df.to_csv(self.image_dir+'/images.csv')
        if not (image.get_background() is None):
            PILImage.fromarray(image.get_background(),"L").save(bgnd_filepath)
        holo = image.get_hologram()
        if not (holo is None):
            holo = np.uint16(holo*65535)
            red = np.uint8(holo % 256)
            green = np.uint8((holo - red)/256)
            blue = np.uint8(np.zeros(holo.shape))
            rgb = np.dstack((red,green,blue))
            PILImage.fromarray(rgb,"RGB").save(holo_filepath)