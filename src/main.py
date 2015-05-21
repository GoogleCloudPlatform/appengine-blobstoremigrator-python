"""
Main WSGI app for blob-migrator tool.
"""
import webapp2

from app.routes import ROUTES

APP = webapp2.WSGIApplication(ROUTES)
