from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm
from flask_gravatar import Gravatar
import os
import forms



app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(8)
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


login_manager = LoginManager()
login_manager.init_app(app=app)


gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


def get_author_name(id):
    user = db.session.query(User).filter(User.id == int(id)).first()
    return user.name


######### testing decorative function: #########
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.get_id() != "1":
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)
    return decorated_function


def get_email_by_id(id):
    user = db.session.query(User).filter(User.id == int(id)).first()
    return user.email


# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         #If id is not 1 then return abort with 403 error
#         if current_user.get_id():
#             flash("You need to login in order to leave a comment.")
#             return redirect(url_for('login'))
#         #Otherwise continue with the route function
#         return f(*args, **kwargs)
#     return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


##CONFIGURE TABLES


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # ***************Parent Relationship*************#
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")

    # ***************Child Relationship*************#
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    text = db.Column(db.Text, nullable=False)


with app.app_context():
    db.create_all()


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, get_name=get_author_name)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = forms.CreateRegisterForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        real_password = form.password.data

        db_user = db.session.query(User).filter(User.email == email).first()
        if db_user:
            flash("You have already signed up with that email address.")
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(real_password, method="pbkdf2:sha256", salt_length=8)

        user = User(name=name, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        login_user(user=user)
        return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = forms.CreateLogInForm()
    if form.validate_on_submit():
        email = form.email.data
        real_password = form.password.data
        user = db.session.query(User).filter(User.email == email).first()
        if user:
            if not check_password_hash(user.password, real_password):
                flash("Password is incorrect.")
            else:
                login_user(user=user)
                return redirect(url_for('get_all_posts'))
        else:
            flash("There is no user with that email.")
    return render_template("login.html", form= form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    comments = db.session.query(Comment).filter(Comment.post_id == post_id).all()
    form = forms.CreateCommentForm()
    if form.validate_on_submit():
        comment_text = form.comment.data
        if not current_user.get_id():
            flash("You have to be logged in to leave a comment.")
            return redirect(url_for('login'))
        else:
            comment = Comment(author_id=current_user.get_id(), post_id=post_id, text=comment_text)
            db.session.add(comment)
            db.session.commit()
        return redirect(url_for('get_all_posts'))

    requested_post = BlogPost.query.get(post_id)
    return render_template("post.html", post=requested_post,
                           get_name= get_author_name, form=form, comments=comments, get_email_by_id=get_email_by_id)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=['GET', 'POST'])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=int(current_user.get_id()),
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
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
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
