# -*- coding: utf-8 -*-

import sys
import os

sys.path.pop(0)
sys.path.insert(0, os.getcwd())

from flask import current_app
from werkzeug.local import LocalProxy

from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.security import Security, UserMixin, RoleMixin, \
     SQLAlchemyUserDatastore, current_user
from flask_security.acl import grant_object_access, grant_class_access
from flask_security.decorators import is_granted

from tests.test_app import create_app as create_base_app, populate_data, \
     add_context_processors

_security = LocalProxy(lambda: current_app.extensions['security'])

def populate_acl_data(db, User, Post, Comment):
    matt = User.query.filter_by(email='matt@lp.com').first()
    joe = User.query.filter_by(email='joe@lp.com').first()
    tiya = User.query.filter_by(email='tiya@lp.com').first()

    matts_post = Post(body='matt@lp.com post content', author=matt, comments=[Comment(body='tiya@lp.com comment content', author=tiya)])
    joes_post = Post(body='joe@lp.com post content', author=joe, comments=[Comment(body='matt@lp.com comment content', author=matt)])
    tiyas_post = Post(body='tiya@lp.com post content', author=tiya, comments=[Comment(body='joe@lp.com comment content', author=joe)])

    for m in matts_post, joes_post, tiyas_post:
        db.session.add(m)

    db.session.commit()

    grant_object_access(matt, matts_post, ['owner'])
    grant_object_access(joe, joes_post, ['owner'])
    grant_object_access(tiya, tiyas_post, ['owner'])


def create_app(config, **kwargs):
    app = create_base_app(config)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'

    db = SQLAlchemy(app)

    roles_users = db.Table('roles_users',
        db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
        db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))

    class Role(db.Model, RoleMixin):
        id = db.Column(db.Integer(), primary_key=True)
        name = db.Column(db.String(80), unique=True)
        description = db.Column(db.String(255))

    class User(db.Model, UserMixin):
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(255), unique=True)
        password = db.Column(db.String(255))
        last_login_at = db.Column(db.DateTime())
        current_login_at = db.Column(db.DateTime())
        last_login_ip = db.Column(db.String(100))
        current_login_ip = db.Column(db.String(100))
        login_count = db.Column(db.Integer)
        active = db.Column(db.Boolean())
        confirmed_at = db.Column(db.DateTime())
        roles = db.relationship('Role', secondary=roles_users,
                                backref=db.backref('users', lazy='dynamic'))

    class Post(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        body = db.Column(db.String(255))
        author_id = db.Column(db.ForeignKey('user.id'))
        author = db.relationship('User', backref='posts')

    class Comment(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        body = db.Column(db.String(255))
        author_id = db.Column(db.ForeignKey('user.id'))
        author = db.relationship('User', backref='comments')
        post_id = db.Column(db.ForeignKey('post.id'))
        post = db.relationship('Post', backref='comments')

    datastore = SQLAlchemyUserDatastore(db, User, Role, acl_datastore=True)
    app.security = Security(app, datastore=datastore, **kwargs)
    add_context_processors(app.security)

    @app.route('/posts', methods=['POST'])
    def posts():
        user = current_user._get_current_object()
        post = Post(body='%s post content' % user.email, author=user)
        db.session.add(post)
        db.session.commit()
        grant_object_access(user, post, ['owner'])
        return post.body

    @app.route('/posts/<post_id>')
    @is_granted(Post, 'admin')
    def show_post(post_id):
        return Post.query.get_or_404(post_id).body

    @app.route('/posts/<post_id>/comments')
    def post_comments(post_id):
        post = Post.query.get_or_404(post_id)
        return '\n'.join(['<div>%s</div>' % c.body for c in post.comments])

    @app.before_first_request
    def before_first_request():
        db.drop_all()
        db.create_all()
        populate_data(app.config.get('USER_COUNT', None))
        populate_acl_data(db, User, Post, Comment)

    return app

if __name__ == '__main__':
    create_app({}).run()
