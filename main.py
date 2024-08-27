from __future__ import annotations
from datetime import date
from hashlib import md5
from flask import Flask, abort, render_template, redirect, url_for, flash, request,current_app, session
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm  # Importing forms from forms.py
from typing import List
import hashlib
import smtplib
import os
from dotenv import load_dotenv
load_dotenv()

EMAIL=os.getenv('my_email')
PASSWORD=os.getenv('EMAIL_PASSWORD')


# TODO: Creating @admin_only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if the user is authenticated and is admin
        if not current_user.is_authenticated or current_user.email != 'admin@gmail.com':
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function



# TODO: Initializing Flask app and extensions
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_KEY')
app.config['GRAVATAR_SIZE'] = 30
app.config['GRAVATAR_RATING'] = 'g'  
app.config['GRAVATAR_DEFAULT'] = 'retro'  
ckeditor = CKEditor(app)
Bootstrap5(app)



# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)  # Properly initializing the login manager with the app

# Create a user_loader callback
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

#TODO: INTIALIZING GRAVATAR
def gravatar(email: str, size: int = 100, rating: str = 'g', default: str = 'retro', 
             force_default: bool = False, force_lower: bool = False, use_ssl: bool = False, 
             base_url: str = None) -> str:
    if email is None:
        email = ''  # Default to an empty string if email is None
    if force_lower:
        email = email.lower()
    email_hash = hashlib.md5(email.encode('utf-8')).hexdigest()  # Safely encode email
    url = base_url if base_url else ('https://secure.gravatar.com/avatar/' if use_ssl else 'http://www.gravatar.com/avatar/')
    url += email_hash
    url += f'?s={size}&r={rating}&d={default}'
    if force_default:
        url += '&f=y'
    return url




#TODO: Creating DeclarativeBase
class Base(DeclarativeBase):
    pass

# TODO: Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///DAY_69_BlogPosts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Suppress warning about SQLAlchemy events
db = SQLAlchemy(model_class=Base)
db.init_app(app)



# TODO: Define User, BlogPost, and Comment models
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    post_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))  # Corrected type to Mapped[int]
    parent_post = relationship("BlogPost", back_populates="comments")
    text: Mapped[str] = mapped_column(Text, nullable=False)


# Initialize database and create tables
with app.app_context():
    db.create_all()


# TODO: Implement user registration with password hashing
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = request.form.get('email')
        result = db.session.execute(db.select(User).where(User.email == email))
        user = result.scalar()
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        # Hash password for new users
        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    
    return render_template("register.html", form=form, logged_in=False)


# TODO: Implement user login with password check
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        # session['user_email'] = email
        password = form.password.data
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("That Email doesn't exist. Try Again!")
            return redirect(url_for('login'))
        elif check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("get_all_posts"))
        else:
            flash('Password incorrect, Try again!')

    return render_template("login.html", form=form, logged_in=False)


#TODO: Configuring Gravatar
@app.context_processor
def inject_gravatar():
    # Retrieve the current user's email from the session or current_user
    email = current_user.email if current_user.is_authenticated else None  
    size = current_app.config['GRAVATAR_SIZE']
    rating = current_app.config['GRAVATAR_RATING']
    default = current_app.config['GRAVATAR_DEFAULT']

    # Generate Gravatar URL
    gravatar_url = gravatar(email, size=size, rating=rating, default=default)
    return {'gravatar': gravatar_url}


# TODO: Implement logout functionality
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


# TODO: Fetch and display all blog posts
@app.route('/')
def get_all_posts():
    # Query the database for all the posts and convert to a python list
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=['POST', 'GET'])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    form = CommentForm()
    

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You must login to comment on the post")
            return redirect(url_for('login'))

        new_comment = Comment(
            text=form.body.data,
            comment_author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
        
    return render_template("post.html", post=requested_post, current_user=current_user, form=form)


# TODO: Allow only admin user to create a new post
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
    return render_template("make-post.html", form=form)


# TODO: Allow only admin user to edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
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
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Allow only admin user to delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# Static pages
@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        data = request.form
        name=data["name"]
        email=data["email"]
        phone_no=data["phone"]
        message=data["message"]
        
        msg_data=(
            f"Subject: New Msg Alert\n\n"
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"Phone_NO: {phone_no}\n"
            f"{message}"
        )
        #sending email....
        with smtplib.SMTP('smtp.gmail.com') as connection:
            connection.starttls()
            connection.login(user=EMAIL, password=PASSWORD)
            connection.sendmail(from_addr=email, to_addrs="kushalbro82@gmail.com", msg=msg_data)
        # with smtplib.SMTP("smtp.gmail.com") as connection:
        #     connection.starttls()
        #     connection.login(user  = email, password=password)
        #     connection.sendmail(from_addr=email, to_addrs="kushalbro82@gmail.com",msg=msg_data)
            
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)


# TODO: Method to display older posts
@app.route('/older_post')
def older_post():
    return render_template("olderpost.html")


if __name__ == "__main__":
    app.run(debug=True, port=5002)
