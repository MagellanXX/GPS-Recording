[app]
title = Fahrtenbuch GPS
package.name = fahrtenbuch
package.domain = org.gpstracker.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3,kivy==2.3.0,plyer,requests,urllib3,certifi,kivy-garden,kivy_garden.mapview
orientation = portrait
fullscreen = 0
android.permissions = ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,FOREGROUND_SERVICE,FOREGROUND_SERVICE_LOCATION
android.api = 33
android.minapi = 21
android.accept_sdk_license = True
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 0
