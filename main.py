import datetime
import math
import os
import sqlite3
import time
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.recycleview import RecycleView
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy_garden.mapview import MapMarker, MapView
from plyer import gps

DB_FILE = os.path.join(os.path.dirname(__file__), "trips.db")


# --- DATENBANK-LOGIK ---
def init_db():
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("""CREATE TABLE IF NOT EXISTS trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    distance_km REAL,
                    duration_str TEXT,
                    avg_speed REAL,
                    max_speed REAL
                )""")
  conn.commit()
  conn.close()


def save_trip(
    start_time, end_time, dist_km, duration_str, avg_speed, max_speed
):
  if dist_km < 0.01:
    return  # Winzige Messfehler/Tests unter 10 Metern nicht speichern
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  date_str = datetime.datetime.now().strftime("%Y-%m-%d")
  s_time = datetime.datetime.fromtimestamp(start_time).strftime("%H:%M")
  e_time = datetime.datetime.fromtimestamp(end_time).strftime("%H:%M")
  c.execute(
      """INSERT INTO trips 
                 (date, start_time, end_time, distance_km, duration_str, avg_speed, max_speed)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
      (date_str, s_time, e_time, dist_km, duration_str, avg_speed, max_speed),
  )
  conn.commit()
  conn.close()


def get_all_trips():
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute(
      "SELECT date, start_time, end_time, distance_km, duration_str, avg_speed,"
      " max_speed FROM trips ORDER BY id DESC"
  )
  rows = c.fetchall()
  conn.close()
  return rows


# --- UI-HILFSKOMPONENTEN ---
class CardBox(BoxLayout):

  def __init__(self, bg_color=(0.14, 0.16, 0.20, 1), **kwargs):
    super().__init__(**kwargs)
    self.bg_color = bg_color
    self.padding = [12, 8]
    self.orientation = "vertical"
    self.bind(pos=self._update_canvas, size=self._update_canvas)

  def _update_canvas(self, *args):
    self.canvas.before.clear()
    with self.canvas.before:
      Color(*self.bg_color)
      RoundedRectangle(pos=self.pos, size=self.size, radius=[12])


# --- TRACKING ENGINE ---
class TrackerEngine:

  def __init__(self):
    self.is_tracking = False
    self.start_time = None
    self.last_lat = None
    self.last_lon = None
    self.current_lat = 53.33  # Standard: Deutschland / Mitte
    self.current_lon = 8.48
    self.total_distance_m = 0.0
    self.current_speed_kmh = 0.0
    self.max_speed_kmh = 0.0
    self.route_points = []

  def start(self):
    self.is_tracking = True
    self.start_time = time.time()
    self.total_distance_m = 0.0
    self.current_speed_kmh = 0.0
    self.max_speed_kmh = 0.0
    self.last_lat = None
    self.last_lon = None
    self.route_points = []
    try:
      gps.configure(on_location=self.on_location)
      gps.start(minTime=1000, minDistance=1)
    except Exception as e:
      print(f"GPS Init Error: {e}")

  def stop(self):
    if not self.is_tracking:
      return
    self.is_tracking = False
    end_time = time.time()
    try:
      gps.stop()
    except Exception:
      pass

    stats = self.get_stats()
    save_trip(
        self.start_time,
        end_time,
        float(stats["dist_km"]),
        stats["time_str"],
        float(stats["avg_speed_kmh"]),
        float(stats["max_speed_kmh"]),
    )

  def on_location(self, **kwargs):
    lat = kwargs.get("lat")
    lon = kwargs.get("lon")
    speed_ms = kwargs.get("speed", 0.0)

    self.current_lat = lat
    self.current_lon = lon
    self.route_points.append((lat, lon))

    if speed_ms is not None and speed_ms > 0:
      self.current_speed_kmh = speed_ms * 3.6
      if self.current_speed_kmh > self.max_speed_kmh:
        self.max_speed_kmh = self.current_speed_kmh
    else:
      self.current_speed_kmh = 0.0

    if self.last_lat is not None and self.last_lon is not None:
      d = self._haversine(self.last_lat, self.last_lon, lat, lon)
      if d > 0.8:
        self.total_distance_m += d

    self.last_lat = lat
    self.last_lon = lon

  def _haversine(self, lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
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
        "max_speed_kmh": f"{self.max_speed_kmh:.1f}",
    }


# --- SCREEN 1: COCKPIT / DASHBOARD ---
class DashboardScreen(Screen):

  def __init__(self, tracker, **kwargs):
    super().__init__(**kwargs)
    self.tracker = tracker
    self.user_marker = None

    root = BoxLayout(orientation="vertical", padding=14, spacing=10)
    with root.canvas.before:
      Color(0.07, 0.08, 0.11, 1)
      self.bg = RoundedRectangle(pos=root.pos, size=root.size)
    root.bind(
        pos=lambda i, v: setattr(self.bg, "pos", v),
        size=lambda i, v: setattr(self.bg, "size", v),
    )

    # 1. Header mit Navigations-Button zur Historie
    nav_bar = BoxLayout(size_hint_y=0.08)
    title = Label(
        text="FAHRTENBUCH",
        font_size="20sp",
        bold=True,
        color=(0.95, 0.96, 0.98, 1),
    )
    btn_history = Button(
        text="Historie ➔",
        size_hint_x=0.35,
        font_size="13sp",
        bold=True,
        background_normal="",
        background_color=(0.2, 0.25, 0.35, 1),
    )
    btn_history.bind(on_press=self.go_to_history)
    nav_bar.add_widget(title)
    nav_bar.add_widget(btn_history)
    root.add_widget(nav_bar)

    # 2. Tacho-Kachel
    speed_card = CardBox(
        bg_color=(0.11, 0.14, 0.20, 1), size_hint_y=0.22, spacing=2
    )
    lbl_speed_title = Label(
        text="AKTUELLES TEMPO",
        font_size="11sp",
        bold=True,
        color=(0.22, 0.65, 0.95, 1),
        size_hint_y=0.2,
    )
    self.val_speed = Label(
        text="0.0",
        font_size="48sp",
        bold=True,
        color=(1, 1, 1, 1),
        size_hint_y=0.6,
    )
    lbl_unit = Label(
        text="km/h",
        font_size="12sp",
        color=(0.5, 0.55, 0.65, 1),
        size_hint_y=0.2,
    )
    speed_card.add_widget(lbl_speed_title)
    speed_card.add_widget(self.val_speed)
    speed_card.add_widget(lbl_unit)
    root.add_widget(speed_card)

    # 3. Eingebettete Kartenansicht
    self.map_view = MapView(
        zoom=15,
        lat=self.tracker.current_lat,
        lon=self.tracker.current_lon,
        size_hint_y=0.32,
    )
    root.add_widget(self.map_view)

    # 4. 2x2 Statistik-Kacheln
    grid = GridLayout(cols=2, spacing=8, size_hint_y=0.24)

    c_dist = CardBox()
    c_dist.add_widget(
        Label(
            text="DISTANZ",
            font_size="10sp",
            bold=True,
            color=(0.55, 0.6, 0.7, 1),
            size_hint_y=0.3,
        )
    )
    self.val_dist = Label(
        text="0.00 km",
        font_size="18sp",
        bold=True,
        color=(0.95, 0.95, 0.95, 1),
        size_hint_y=0.7,
    )
    c_dist.add_widget(self.val_dist)

    c_time = CardBox()
    c_time.add_widget(
        Label(
            text="FAHRZEIT",
            font_size="10sp",
            bold=True,
            color=(0.55, 0.6, 0.7, 1),
            size_hint_y=0.3,
        )
    )
    self.val_time = Label(
        text="00:00:00",
        font_size="18sp",
        bold=True,
        color=(0.95, 0.95, 0.95, 1),
        size_hint_y=0.7,
    )
    c_time.add_widget(self.val_time)

    c_avg = CardBox()
    c_avg.add_widget(
        Label(
            text="Ø TEMPO",
            font_size="10sp",
            bold=True,
            color=(0.55, 0.6, 0.7, 1),
            size_hint_y=0.3,
        )
    )
    self.val_avg = Label(
        text="0.0 km/h",
        font_size="17sp",
        bold=True,
        color=(0.95, 0.95, 0.95, 1),
        size_hint_y=0.7,
    )
    c_avg.add_widget(self.val_avg)

    c_max = CardBox()
    c_max.add_widget(
        Label(
            text="MAX TEMPO",
            font_size="10sp",
            bold=True,
            color=(0.55, 0.6, 0.7, 1),
            size_hint_y=0.3,
        )
    )
    self.val_max = Label(
        text="0.0 km/h",
        font_size="17sp",
        bold=True,
        color=(0.95, 0.95, 0.95, 1),
        size_hint_y=0.7,
    )
    c_max.add_widget(self.val_max)

    grid.add_widget(c_dist)
    grid.add_widget(c_time)
    grid.add_widget(c_avg)
    grid.add_widget(c_max)
    root.add_widget(grid)

    # 5. Start / Stopp Button
    self.btn_toggle = Button(
        text="STARTEN",
        font_size="18sp",
        bold=True,
        size_hint_y=0.12,
        background_normal="",
        background_color=(0.15, 0.78, 0.45, 1),
    )
    self.btn_toggle.bind(on_press=self.toggle_tracking)
    root.add_widget(self.btn_toggle)

    self.add_widget(root)
    Clock.schedule_interval(self.update_ui, 0.5)

  def toggle_tracking(self, instance):
    if not self.tracker.is_tracking:
      self.tracker.start()
      self.btn_toggle.text = "STOPPEN & SPEICHERN"
      self.btn_toggle.background_color = (0.9, 0.25, 0.28, 1)
    else:
      self.tracker.stop()
      self.btn_toggle.text = "STARTEN"
      self.btn_toggle.background_color = (0.15, 0.78, 0.45, 1)

  def update_ui(self, dt):
    if self.tracker.is_tracking:
      stats = self.tracker.get_stats()
      self.val_speed.text = stats["speed_kmh"]
      self.val_dist.text = f"{stats['dist_km']} km"
      self.val_time.text = stats["time_str"]
      self.val_avg.text = f"{stats['avg_speed_kmh']} km/h"
      self.val_max.text = f"{stats['max_speed_kmh']} km/h"

      # Karte auf aktuelle Position zentrieren & Marker setzen
      lat, lon = self.tracker.current_lat, self.tracker.current_lon
      self.map_view.center_on(lat, lon)
      if not self.user_marker:
        self.user_marker = MapMarker(lat=lat, lon=lon)
        self.map_view.add_marker(self.user_marker)
      else:
        self.user_marker.lat = lat
        self.user_marker.lon = lon

  def go_to_history(self, instance):
    self.manager.get_screen("history").refresh_data()
    self.manager.current = "history"


# --- SCREEN 2: HISTORIE ---
class HistoryScreen(Screen):

  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.root_box = BoxLayout(orientation="vertical", padding=14, spacing=10)
    with self.root_box.canvas.before:
      Color(0.07, 0.08, 0.11, 1)
      self.bg = RoundedRectangle(pos=self.root_box.pos, size=self.root_box.size)
    self.root_box.bind(
        pos=lambda i, v: setattr(self.bg, "pos", v),
        size=lambda i, v: setattr(self.bg, "size", v),
    )

    # Header
    nav_bar = BoxLayout(size_hint_y=0.08)
    btn_back = Button(
        text="⬅ Zurück",
        size_hint_x=0.3,
        font_size="13sp",
        bold=True,
        background_normal="",
        background_color=(0.2, 0.25, 0.35, 1),
    )
    btn_back.bind(on_press=self.go_back)
    title = Label(
        text="FAHRTEN-HISTORIE",
        font_size="18sp",
        bold=True,
        color=(0.95, 0.96, 0.98, 1),
    )
    nav_bar.add_widget(btn_back)
    nav_bar.add_widget(title)
    self.root_box.add_widget(nav_bar)

    # Scrollbarer Container für Fahrten
    self.scroll_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
    self.scroll_layout.bind(minimum_height=self.scroll_layout.setter("height"))

    self.rv = RecycleView(size_hint_y=0.92)
    self.rv.add_widget(self.scroll_layout)
    self.root_box.add_widget(self.rv)

    self.add_widget(self.root_box)

  def refresh_data(self):
    self.scroll_layout.clear_widgets()
    trips = get_all_trips()

    if not trips:
      empty_lbl = Label(
          text="Noch keine aufgezeichneten Fahrten vorhanden.",
          color=(0.5, 0.55, 0.65, 1),
          size_hint_y=None,
          height=60,
      )
      self.scroll_layout.add_widget(empty_lbl)
      return

    current_month = None
    for trip in trips:
      date, s_time, e_time, dist, dur, avg_spd, max_spd = trip

      # Gruppierung nach Monat / Jahr (z.B. August 2026)
      try:
        t_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
        month_str = t_obj.strftime("%B %Y")
      except Exception:
        month_str = date

      if month_str != current_month:
        current_month = month_str
        m_header = Label(
            text=f"📅 {current_month}",
            font_size="15sp",
            bold=True,
            color=(0.22, 0.65, 0.95, 1),
            size_hint_y=None,
            height=35,
        )
        self.scroll_layout.add_widget(m_header)

      # Eintragskarte
      card = CardBox(size_hint_y=None, height=75)
      line1 = BoxLayout()
      line1.add_widget(
          Label(
              text=f"{date}  ({s_time} - {e_time})",
              bold=True,
              font_size="13sp",
              color=(1, 1, 1, 1),
          )
      )
      line1.add_widget(
          Label(
              text=f"{dist:.2f} km",
              bold=True,
              font_size="15sp",
              color=(0.15, 0.78, 0.45, 1),
          )
      )

      line2 = BoxLayout()
      line2.add_widget(
          Label(
              text=f"Dauer: {dur}",
              font_size="11sp",
              color=(0.6, 0.65, 0.75, 1),
          )
      )
      line2.add_widget(
          Label(
              text=f"Ø {avg_spd:.1f} km/h (Max: {max_spd:.1f})",
              font_size="11sp",
              color=(0.6, 0.65, 0.75, 1),
          )
      )

      card.add_widget(line1)
      card.add_widget(line2)
      self.scroll_layout.add_widget(card)

  def go_back(self, instance):
    self.manager.current = "dashboard"


# --- HAUPT-APP ---
class GPSApp(App):

  def build(self):
    init_db()
    tracker = TrackerEngine()
    sm = ScreenManager()
    sm.add_widget(DashboardScreen(tracker, name="dashboard"))
    sm.add_widget(HistoryScreen(name="history"))
    return sm


if __name__ == "__main__":
  GPSApp().run()
