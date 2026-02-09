from flask import Blueprint, render_template, request, redirect, flash, url_for
from flask_login import login_required, current_user
from ..models import db, Playlist
from .. import db

playlists_bp = Blueprint('playlists', __name__)

@playlists_bp.route('/playlists')
@login_required
def index():
    playlists = Playlist.query.all()
    return render_template('playlists.html', playlists=playlists)

@playlists_bp.route('/playlists/add', methods=['POST'])
@login_required
def add_playlist():
    name = request.form.get('name')
    url = request.form.get('url')
    username = request.form.get('username')
    password = request.form.get('password')
    notes = request.form.get('notes')
    
    if not name or not url:
        flash('Name and URL are required', 'error')
        return redirect(url_for('playlists.index'))
    
    new_playlist = Playlist(
        name=name, 
        url=url, 
        username=username, 
        password=password,
        notes=notes
    )
    db.session.add(new_playlist)
    db.session.commit()
    flash('Playlist added successfully', 'success')
    return redirect(url_for('playlists.index'))

@playlists_bp.route('/playlists/delete/<int:id>', methods=['POST'])
@login_required
def delete_playlist(id):
    playlist = Playlist.query.get_or_404(id)
    db.session.delete(playlist)
    db.session.commit()
    flash('Playlist deleted successfully', 'success')
    return redirect(url_for('playlists.index'))

@playlists_bp.route('/playlists/toggle/<int:id>', methods=['POST'])
@login_required
def toggle_status(id):
    playlist = Playlist.query.get_or_404(id)
    playlist.status = 'disabled' if playlist.status == 'active' else 'active'
    db.session.commit()
    flash(f"Playlist {playlist.name} is now {playlist.status}", 'success')
    return redirect(url_for('playlists.index'))


@playlists_bp.route('/client-playlist')
def client_playlist():
    """
    Client-facing playlist browser with categories.
    Shows Live TV, Movies, Series grouped by category.
    """
    username = request.args.get('username')
    password = request.args.get('password')
    category = request.args.get('category')
    
    return render_template('client_playlist.html', 
                         username=username,
                         password=password,
                         category=category)
