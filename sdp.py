from gi.repository import Gtk, GdkPixbuf, GObject
#from gi.repository import Gst as gst
import threading
import time
import sched
import urllib2
import gst
import datetime
from threading import Timer
#import gobject

#import pyglet
#import pygst
import soundcloud

class MainWindow:
  def __init__(self):
    self.builder = Gtk.Builder()
    self.builder.add_from_file("sdp.glade")
    self.builder.connect_signals(self)

    self.player = gst.element_factory_make("playbin", "player")

    # Start watching for GST signals
#    bus = self.player.get_bus()
#    bus.add_signal_watch()
#    bus.connect("message", self.on_gst_message)

    self.current_track_id = None

    self.client = soundcloud.Client(client_id="fddd281b41e49cbfef36d3319532ac9c")

    window = self.builder.get_object("window_sdp")
    window.show_all()

#  def on_gst_message(self, bus, message):
#    print message.type

  def search(self, term=""):
    self.tracks = self.client.get('/tracks', limit=15, q=term, filter="streamable")

    liststore1 = self.builder.get_object("liststore1")
    liststore1.clear()

    i = 0
    for t in self.tracks:
      liststore1.append([i, t.title, t.permalink_url])
      i+=1

  def on_search_song_activate(self, search_entry):
      self.search(search_entry.get_text())

#  def on_window_key_release_event(self, widget, event):
#      return True
#      print event.keyval

  def on_window_destroy(self, a):
      self.player.set_state(gst.STATE_NULL)
      Gtk.main_quit()

  def on_btn_play_toggled(self, button):
      if (button.get_active()):
        self.player.set_state(gst.STATE_PLAYING)
      else:
        self.player.set_state(gst.STATE_PAUSED)

  def on_btn_stop_clicked(self, button):
      self.player.set_state(gst.STATE_NULL)
      self.reset_playing()

  def on_btn_next_clicked(self, button):
      if (self.current_track_id == None):
        n_id = 0
      else:
        n_id = self.current_track_id+1

      tv_songs = self.builder.get_object("tv_songs")
      #path, col = tv_songs.get_cursor()
      #tv_songs.get_model().next()
      selection = tv_songs.get_selection()
#      path = Gtk.TreePath.new_first()
      #path = Gtk.TreePath.new_from_string(str(n_id))
      #selection.select_path(path)

      tv_songs.set_cursor(n_id, 0)
      path, col = tv_songs.get_cursor()
      tv_songs.row_activated(path, col)

  def reset_image(self):
      self.builder.get_object("image1").set_from_file("soundcloud_logo_small.png")

  def reset_playing(self):
      self.builder.get_object("l_artist").set_text("")
      self.builder.get_object("l_title").set_text("")


  def on_songs_row_activated(self, treeview, row_id, column):
      (model, i) = treeview.get_selection().get_selected()

      track_id = model.get_value(i, 0)
      track = self.tracks[track_id]

      self.builder.get_object("l_title").set_markup("<span size=\"large\" font_weight=\"bold\">" + track.title + "</span>")
      self.builder.get_object("l_artist").set_markup("<span size=\"large\">" + track.user['username'] + "</span>")

      print "streamable: " + str(track.streamable)

      if (track.artwork_url != None):
       # print "getting artwork " + track.artwork_url
      
        #th = threading.Thread(target=self.update_from_thread)
        th_img = threading.Thread(target=self.update_from_thread,args=(track.artwork_url,))
        #th_img.daemon = True
        th_img.start()
      else:
        self.reset_image()

      th_play = threading.Thread(target=self.play,args=(track_id,))
      th_play.daemon = True
      th_play.start()

#      Timer(0.5, self.update_time).start()

#      s = sched.scheduler(time.time, time.sleep)
#      s.enter(60, 1, self.update_time, (s,))

      th_st = threading.Thread(target=self.update_time)
      th_st.daemon = True
      th_st.start()
#      s.run()


  def update_from_thread(self, url):
      #print url
      response = urllib2.urlopen(url).read()
      #print len(response)
      l = GdkPixbuf.PixbufLoader.new_with_type('jpeg')
      l.write(response)
      l.close()

      self.builder.get_object("image1").set_from_pixbuf(l.get_pixbuf())

  def play(self, track_id):
      self.current_track_id = track_id
      url = self.client.get(self.tracks[track_id].stream_url, allow_redirects=False)
      print url.location

      self.player.set_state(gst.STATE_NULL)
      self.player.set_property('uri', url.location)
      self.player.set_state(gst.STATE_PLAYING)


      #self.builder.get_object("btn_play").set_active(True)

      #self.builder.get_object("label1").set_text(self.tracks[row_id].title)
      #print self.tracks[row_id]

      #for path in pathlist:
      #  tree_iter = model.get_iter(path)
      #  value = model.get_value(tree_iter, 0)
        #open_(value)
      #  print value.duration

      #  self.scale_position.set_range(0, value.duration)
        
       # if (value.artwork_url != None):
       #   print "getting artwork"
       #   response = urllib2.urlopen(value.artwork_url).read()
       #   print response.__class__.__name__
       #   Pixbuf.new_from_data(response, GdkPixbuf.Colorspace.RGB, False, 70, 100, 100, 0, None, None)

          #Pixbuf.new_fromi_file(response
      

  def update_time(self):
    correct_states = [gst.STATE_PLAYING, gst.STATE_PAUSED]
    format = gst.Format(gst.FORMAT_TIME)

    self.builder.get_object("l_length").set_text(str(datetime.timedelta(seconds=(0 / gst.SECOND))))

    while True:

      while (self.player.get_state()[1] not in correct_states):
        time.sleep(0.1)
    
      duration = self.player.query_position(format)[0]

      delta = datetime.timedelta(seconds=(duration / gst.SECOND))
      self.builder.get_object("l_length").set_text(str(delta))

      time.sleep(1)
  #    self.update_time()

#      scheduler.enter(1, 1, self.update_time, (scheduler,))

#builder.connect_signals(Handler())


GObject.threads_init()
MainWindow()
Gtk.main()
