from . import db
from flask_login import UserMixin
from datetime import datetime

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

class StreamUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False) # Apache/Bcrypt format for .htpasswd sync
    status = db.Column(db.String(20), default='active') # active, disabled
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    def to_htpasswd_line(self):
        """Returns the line formatted for .htpasswd file"""
        # Note: In a real implementation, we'd use passlib here to ensure we write the correct
        # compatible hash (e.g. APR1 or Bcrypt) that Nginx expects.
        return f"{self.username}:{self.password_hash}"

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    username = db.Column(db.String(80), nullable=True) # Optional, if we parse it
    password = db.Column(db.String(80), nullable=True) # Optional
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
