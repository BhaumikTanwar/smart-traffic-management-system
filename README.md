---
title: Smart Traffic Management System
emoji: 🚦
colorFrom: orange
colorTo: red
sdk: docker
pinned: false
app_port: 7860
---

# Smart Traffic Management System

A real-time traffic monitoring and congestion management system built with Flask, YOLOv8, and Leaflet.js.

## Features
- Vehicle detection via YOLOv8 (recorded video / live camera)
- Spiderweb congestion propagation on real Delhi road networks (OSM/Overpass API)
- Real-time WebSocket updates via Flask-SocketIO
- SQLite logging for traffic and spiderweb data
- Interactive map visualization

## Tech Stack
- **Backend**: Flask, Flask-SocketIO, Gunicorn + Eventlet
- **AI**: YOLOv8n, OpenCV, ByteTrack
- **Frontend**: Leaflet.js, HTML/CSS/JS
- **DB**: SQLite