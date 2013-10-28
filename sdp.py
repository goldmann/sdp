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

from gi.repository import Gtk, Gdk, Gst, GLib, GdkPixbuf, GObject
import logging
import threading
import time
import webbrowser
import urllib2
import datetime
import sys
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
    self.playbin = Gst.ElementFactory.make("playbin", "player")
    self.log.debug("GStreamer player ready")

    self.current_iter = None
    self.current_track_id = None

    self.pipeline = Gst.Pipeline()

    self.bus = self.pipeline.get_bus()
    self.bus.add_signal_watch()
    self.bus.connect('message::eos', self.on_eos)

    self.pipeline.add(self.playbin)

    self.sc = SoundCloud()

    self.treeview = self.builder.get_object("tv_songs")
    self.model = self.treeview.get_model()

    window = self.builder.get_object("window_main")
    window.show_all()

  def on_eos(self, bus, message):
    self.play_next()

  def play_previous(self):
    i = self.model.iter_previous(self.current_iter)
    self.activate_row(i)

  def play_next(self):
    i = self.model.iter_next(self.current_iter)
    self.activate_row(i)

  def activate_row(self, i):
    if i != None:
      tp = self.model.get_path(i)
      self.treeview.row_activated(tp, self.builder.get_object("treeviewcolumn1"))

  def on_window_key_press_event(self, window, key):
    if key.state == Gdk.ModifierType.CONTROL_MASK:
      # Play/pause
      if key.keyval == Gdk.KEY_space:
        if self.pipeline.get_state(0)[1] == Gst.State.PAUSED:
          self.pipeline.set_state(Gst.State.PLAYING)
        else:
          self.pipeline.set_state(Gst.State.PAUSED)

      # Next song
      elif key.keyval == Gdk.KEY_rightarrow or key.keyval == 65363:
        self.play_next()

      # Prev song
      elif key.keyval == Gdk.KEY_leftarrow or key.keyval == 65361:
        self.play_previous()

      # Focus on search
      elif key.keyval == Gdk.KEY_f:
        self.builder.get_object("search_song").grab_focus()

  def search(self, term=""):
    self.tracks = self.sc.tracks(term)

    self.model.clear()

    i = 0
    for t in self.tracks:
      self.model.append([i, t.user['username'], t.title])
      i+=1

  def on_search_song_activate(self, search_entry):
      self.search(search_entry.get_text())

  def on_window_destroy(self, a):
      self.pipeline.set_state(Gst.State.NULL)
      Gtk.main_quit()

  def on_image_artwork_small_button_release_event(self, eventbox, eventbutton):
      window = self.builder.get_object("window_artwork")
      window.show_all()

  def on_image_artwork_button_release_event(self, eventbox, eventbutton):
      window = self.builder.get_object("window_artwork")
      window.hide()
      

  def reset_image(self):
      self.builder.get_object("image_artwork_small").set_from_file("images/soundcloud_logo_small.png")

  def reset_playing(self):
      self.builder.get_object("l_artist").set_text("")
      self.builder.get_object("l_title").set_text("")

  def on_tv_songs_button_press(self, treeview, event):
      # Right click
      if event.button == 3:
        x = int(event.x)
        y = int(event.y)
        time = event.time
        pthinfo = treeview.get_path_at_pos(x, y)
        if pthinfo is not None:
          path, col, cellx, celly = pthinfo
          treeview.grab_focus()
          treeview.set_cursor( path, col, 0)
          self.builder.get_object("tv_menu").popup(None, None, None, None, event.button, time)

  def on_tv_menu_browser_activate(self, a):
      path, column = self.treeview.get_cursor()
      i = self.model.get_iter(path)
      track_id = self.model.get_value(i, 0)
      track = self.tracks[track_id]
      webbrowser.open(track.permalink_url)

  def on_songs_row_activated(self, treeview, path, column):
      i = self.model.get_iter(path)
      self.current_iter = i

      track_id = self.model.get_value(i, 0)
      track = self.tracks[track_id]

      self.log.debug("Preparing to play track '" + track.title + "' by '" + track.user['username'] + "'")

      self.builder.get_object("l_title").set_markup("<span size=\"large\" font_weight=\"bold\">" + GObject.markup_escape_text(track.title).strip() + "</span>")
      self.builder.get_object("l_artist").set_markup("<span size=\"large\">" + GObject.markup_escape_text(track.user['username']).strip() + "</span>")

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
      try:
        response = urllib2.urlopen(url).read()
      except Exception:
        # Whatever
        self.reset_image()
        return False

      l = GdkPixbuf.PixbufLoader.new_with_type('jpeg')
      l.write(response)
      l.close()
      GObject.idle_add(self.update_image, l.get_pixbuf())

  def play(self, track_id):
      self.current_track_id = track_id
      url = self.sc.client.get(self.tracks[track_id].stream_url, allow_redirects=False)

      self.pipeline.set_state(Gst.State.NULL)
      self.playbin.set_property('uri', url.location)
      # Pause for now, so we can prepare to retrieve the state later
      self.pipeline.set_state(Gst.State.PAUSED)

      correct_states = [Gst.State.PAUSED, Gst.State.PLAYING]

      while (self.pipeline.get_state(100)[1] not in correct_states):
        time.sleep(0.1)

      self.pipeline.set_state(Gst.State.PLAYING)
  
      self.update_time(track_id)

  def update_image(self, pixbuf):
      self.builder.get_object("image_artwork_small").set_from_pixbuf(pixbuf)

  def update_label(self, delta):
      self.builder.get_object("l_length").set_text(str(delta))

  def update_time(self, track_id):

    self.builder.get_object("l_length").set_text(str(datetime.timedelta(seconds=(0 / Gst.SECOND))))

    while self.pipeline.get_state(100)[1] != Gst.State.NULL and self.current_track_id == track_id:
      try:
        duration = self.pipeline.query_position(Gst.Format.TIME)[1]
        delta = datetime.timedelta(seconds=(duration / Gst.SECOND))
        GObject.idle_add(self.update_label, delta)
        time.sleep(0.1)
      except Exception as e:
        print e
        # Whatever, it's expected
        break

Gst.init(None)
GObject.threads_init()
MainWindow()
#GLib.threads_init()
Gdk.threads_init()
Gdk.threads_enter()
Gtk.main()
Gdk.threads_leave()
