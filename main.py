import math
import time
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from plyer import gps


class TrackerEngine:

  def __init__(self):
    self.is_tracking = False
    self.start_time = None
    self.last_lat = None
    self.last_lon = None
    self.total_distance_m = 0.0
    self.current_speed_kmh = 0.0

  def start(self):
    self.is_tracking = True
    self.start_time = time.time()
    self.total_distance_m = 0.0
    self.last_lat = None
    self.last_lon = None
    try:
      gps.configure(on_location=self.on_location)
      gps.start(minTime=1000, minDistance=1)
    except Exception as e:
      print(f"GPS Error: {e}")

  def stop(self):
    self.is_tracking = False
    try:
      gps.stop()
    except Exception:
      pass

  def on_location(self, **kwargs):
    lat = kwargs.get("lat")
    lon = kwargs.get("lon")
    speed_ms = kwargs.get("speed", 0.0)

    if speed_ms is not None and speed_ms > 0:
      self.current_speed_kmh = speed_ms * 3.6
    else:
      self.current_speed_kmh = 0.0

    if self.last_lat is not None and self.last_lon is not None:
      d = self._haversine(self.last_lat, self.last_lon, lat, lon)
      if d > 0.5:
        self.total_distance_m += d

    self.last_lat = lat
    self.last_lon = lon

  def _haversine(self, lat1, lon1, lat2, lon2):
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

  def get_stats(self):
    elapsed = (time.time() - self.start_time) if self.start_time else 0
    dist_km = self.total_distance_m / 1000.0
    avg_speed = (dist_km / (elapsed / 3600.0)) if elapsed > 0 else 0.0
    return {
        "time_str": time.strftime("%H:%M:%S", time.gmtime(elapsed)),
        "dist_km": f"{dist_km:.2f}",
        "speed_kmh": f"{self.current_speed_kmh:.1f}",
        "avg_speed_kmh": f"{avg_speed:.1f}",
    }


class GPSApp(App):

  def build(self):
    self.tracker = TrackerEngine()
    self.layout = BoxLayout(
        orientation="vertical", padding=30, spacing=20
    )

    self.lbl_title = Label(
        text="Fahrtenbuch Tracker", font_size="26sp", bold=True
    )
    self.lbl_time = Label(text="Zeit: 00:00:00", font_size="22sp")
    self.lbl_dist = Label(text="Distanz: 0.00 km", font_size="22sp")
    self.lbl_speed = Label(
        text="Tempo: 0.0 km/h\n(Ø: 0.0 km/h)",
        font_size="20sp",
        halign="center",
    )

    self.btn_toggle = Button(
        text="Tracking Starten",
        font_size="22sp",
        bold=True,
        background_color=(0.2, 0.7, 0.3, 1),
    )
    self.btn_toggle.bind(on_press=self.toggle_tracking)

    self.layout.add_widget(self.lbl_title)
    self.layout.add_widget(self.lbl_time)
    self.layout.add_widget(self.lbl_dist)
    self.layout.add_widget(self.lbl_speed)
    self.layout.add_widget(self.btn_toggle)

    Clock.schedule_interval(self.update_ui, 0.5)
    return self.layout

  def toggle_tracking(self, instance):
    if not self.tracker.is_tracking:
      self.tracker.start()
      self.btn_toggle.text = "Stoppen"
      self.btn_toggle.background_color = (0.8, 0.2, 0.2, 1)
    else:
      self.tracker.stop()
      self.btn_toggle.text = "Starten"
      self.btn_toggle.background_color = (0.2, 0.7, 0.3, 1)

  def update_ui(self, dt):
    if self.tracker.is_tracking:
      stats = self.tracker.get_stats()
      self.lbl_time.text = f"Zeit: {stats['time_str']}"
      self.lbl_dist.text = f"Distanz: {stats['dist_km']} km"
      self.lbl_speed.text = (
          f"Tempo: {stats['speed_kmh']} km/h\n(Ø:"
          f" {stats['avg_speed_kmh']} km/h)"
      )


if __name__ == "__main__":
  GPSApp().run()
