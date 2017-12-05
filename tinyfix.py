#!/usr/bin/env python

import etcd3
import flask
import random
import re
import string
import time
import wtforms


etcd = etcd3.client()
FQDN = 'localhost'


def gen_hash():
    hash_string = string.letters + string.digits
    random.seed(time.time())

    return ''.join(random.choice(hash_string) for _ in xrange(8))


def shorten(url):
    my_domain = 'http://{}/{}'
    while True:
        url_hash = gen_hash()
        if etcd.get(url_hash) == (None, None):
            etcd.put(url_hash, url)
            break

    return my_domain.format(FQDN, url_hash)


def unshorten(path):
    long_url = etcd.get(path)[0]

    return False if long_url is None else long_url


DEBUG = True
app = flask.Flask(__name__)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = '7d441f27d441f27567d441f2b6176a'


class TinyFixUrlForm(wtforms.Form):
    max_length = 2048
    url = wtforms.TextField(
        'url:',
        validators=[
            wtforms.validators.InputRequired(message='Empty input'),
            wtforms.validators.Length(
                max=max_length,
                message="Max url's length is {}".format(max_length)
            ),
            wtforms.validators.URL(message='Invalid URL')
        ]
    )


@app.route('/', methods=['GET', 'POST'])
def start_page():
    form = TinyFixUrlForm(flask.request.form)

    if flask.request.method == 'POST':
        if form.validate():
            flask.flash(shorten(url=form.url.data))
        else:
            flask.flash('Error: {}'.format('; '.join(form.url.errors)))

    return flask.render_template('start_page.html', form=form)


@app.route('/<path:short_url>', methods=['GET'])
def find_and_return(short_url):
    if flask.request.host.split(':')[0] != FQDN:
        return 'Unknown HOST header'
    # TODO Compile regexp
    if not re.match('^[a-zA-Z0-9]{8}$', short_url):
        return 'Unknown URL format'

    full_url = unshorten(path=short_url)
    if not full_url:
        return 'Sorry, unknown URL'

    return flask.redirect(location=full_url)


if __name__ == '__main__':
    app.run()
