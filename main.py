from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from functools import wraps
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginInForm, CommentForm
from flask_gravatar import Gravatar
from dotenv import load_dotenv
import os

load_dotenv('venv/.env')
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
gravater = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)


class Users(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    user_comment = relationship("Comment", backref="commenting_user")


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("Users", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    blog_comments = relationship("Comment", backref="comments_on_blog")


# Table for comments
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(2000), nullable=False)
    commenting_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comments_on_blog_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))


db.create_all()


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        else:
            return f(*args, **kwargs)

    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, user_active=current_user.is_active)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        user = Users.query.filter_by(email=email).first()
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        else:
            hash_password = generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8)
            new_user = Users(name=form.name.data, email=email, password=hash_password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form, user_active=current_user.is_active)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginInForm()
    if form.validate_on_submit():
        email = form.email.data
        user = Users.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash('Password incorrect. Please try again!', 'error')
                return redirect(url_for('login'))
        else:
            flash('Email not found. Please check your email and try again!', 'error')
            return redirect(url_for('login'))
    return render_template("login.html", form=form, user_active=current_user.is_active)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if current_user.is_active:
            new_comment = Comment(text=form.comment.data, commenting_user_id=current_user.id, comments_on_blog_id=requested_post.id)
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash('You need to login or register to comment.')
            return redirect(url_for('login'))
    return render_template("post.html", post=requested_post, user_active=current_user.is_active, form=form)


@app.route("/about")
def about():
    return render_template("about.html", user_active=current_user.is_active)


@app.route("/contact")
def contact():
    return render_template("contact.html", user_active=current_user.is_active)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, user_active=current_user.is_active)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = post.author
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, user_active=current_user.is_active)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
