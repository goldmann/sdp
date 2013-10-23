# Copyright (c) 2013 Marek Goldmann
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, GObject
import logging
import threading
import time
import sched
import urllib2
import gst
import datetime
import sys
import gobject as g
from threading import Timer

from client import SoundCloud

class MainWindow:
  def __init__(self):
    self.log = logging.getLogger(self.__class__.__name__)

    ch = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    self.log.addHandler(ch)
    self.log.setLevel(logging.DEBUG)

    self.builder = Gtk.Builder()
    self.builder.add_from_file("sdp.glade")
    self.builder.connect_signals(self)

    self.log.debug("Initializing GStreamer player...")
    self.player = gst.element_factory_make("playbin", "player")
    self.log.debug("GStreamer player ready")

    self.current_iter = None
    self.current_track_id = None

    # Start watching for GST signals
#    bus = self.player.get_bus()
#    bus.add_signal_watch()
#    bus.connect("message", self.on_gst_message)


    self.sc = SoundCloud()

    self.treeview = self.builder.get_object("tv_songs")
    self.model = self.treeview.get_model()

    window = self.builder.get_object("window_main")
    window.show_all()

#  def on_gst_message(self, bus, message):
#    print message.type

  def on_window_key_press_event(self, window, key):
    if key.state == Gdk.ModifierType.CONTROL_MASK:
      # Play/pause
      if key.keyval == Gdk.KEY_space:
        if self.player.get_state()[1] == gst.STATE_PAUSED:
          self.player.set_state(gst.STATE_PLAYING)
        else:
          self.player.set_state(gst.STATE_PAUSED)

      # Next song
      elif key.keyval == Gdk.KEY_rightarrow or key.keyval == 65363:
        i = self.model.iter_next(self.current_iter)
        tp = self.model.get_path(i)
        self.treeview.row_activated(tp, self.builder.get_object("treeviewcolumn1"))

      # Prev song
      elif key.keyval == Gdk.KEY_leftarrow or key.keyval == 65361:
        i = self.model.iter_previous(self.current_iter)
        tp = self.model.get_path(i)
        self.treeview.row_activated(tp, self.builder.get_object("treeviewcolumn1"))

      # Focus on search
      elif key.keyval == Gdk.KEY_s:
        self.builder.get_object("search_song").grab_focus()

  def search(self, term=""):
    self.tracks = self.sc.tracks(term)

    self.model.clear()

    i = 0
    for t in self.tracks:
      self.model.append([i, t.title, t.permalink_url])
      i+=1

  def on_search_song_activate(self, search_entry):
      self.search(search_entry.get_text())

  def on_window_destroy(self, a):
      self.player.set_state(gst.STATE_NULL)
      Gtk.main_quit()

  def reset_image(self):
      self.builder.get_object("image1").set_from_file("images/soundcloud_logo_small.png")

  def reset_playing(self):
      self.builder.get_object("l_artist").set_text("")
      self.builder.get_object("l_title").set_text("")

  def on_songs_row_activated(self, treeview, path, column):
      model = treeview.get_model()
      i = model.get_iter(path)
      self.current_iter = i

      track_id = model.get_value(i, 0)
      track = self.tracks[track_id]

      self.log.debug("Preparing to play track '" + track.title + "' by '" + track.user['username'] + "'")

      self.builder.get_object("l_title").set_markup("<span size=\"large\" font_weight=\"bold\">" + g.markup_escape_text(track.title) + "</span>")
      self.builder.get_object("l_artist").set_markup("<span size=\"large\">" + g.markup_escape_text(track.user['username']) + "</span>")

      self.log.debug("Checking if track contains artwork...")

      if (track.artwork_url != None):
        self.log.debug("Yes it does, will update the image")
      
        th_img = threading.Thread(target=self.get_image,args=(track.artwork_url,))
        th_img.start()
      else:
        self.log.debug("No artwork this time")
        self.reset_image()

      th_play = threading.Thread(target=self.play,args=(track_id,))
      th_play.start()

  def get_image(self, url):
      response = urllib2.urlopen(url).read()
      l = GdkPixbuf.PixbufLoader.new_with_type('jpeg')
      l.write(response)
      l.close()
      GObject.idle_add(self.update_image, l.get_pixbuf())

  def play(self, track_id):
      self.current_track_id = track_id
      url = self.sc.client.get(self.tracks[track_id].stream_url, allow_redirects=False)

      self.player.set_state(gst.STATE_NULL)
      self.player.set_property('uri', url.location)
      # Pause for now, so we can prepare to retrieve the state later
      self.player.set_state(gst.STATE_PAUSED)

      correct_states = [gst.STATE_PLAYING, gst.STATE_PAUSED]

      while (self.player.get_state()[1] not in correct_states):
        time.sleep(0.1)

      self.player.set_state(gst.STATE_PLAYING)
  
      self.update_time()

  def update_image(self, pixbuf):
      self.builder.get_object("image1").set_from_pixbuf(pixbuf)

  def update_label(self, delta):
      self.builder.get_object("l_length").set_text(str(delta))

  def update_time(self):
    format = gst.Format(gst.FORMAT_TIME)

    self.builder.get_object("l_length").set_text(str(datetime.timedelta(seconds=(0 / gst.SECOND))))

    while True:
      try:
        duration = self.player.query_position(format)[0]
      except Exception as e:
        # Whatever, it's expected
        break

      delta = datetime.timedelta(seconds=(duration / gst.SECOND))
  
      GObject.idle_add(self.update_label, delta)

      time.sleep(0.1)

GObject.threads_init()
#Gdk.threads_init()
MainWindow()
#GLib.threads_init()
#Gdk.threads_init()
Gdk.threads_enter()
Gtk.main()
Gdk.threads_leave()
