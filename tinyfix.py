#!/usr/bin/env python

import etcd3
import flask
import flask_socketio
import hashlib
import logging
import random
import re
import string
import wtforms


etcd = etcd3.client()
FQDN = 'localhost'
SHORT_URL_RE = re.compile('^[-_a-zA-Z0-9]{4,8}$')
HASH_STRING = '-_' + string.letters + string.digits

logging.basicConfig(
    format='%(asctime)s %(message)s',
    filename='tinyfix.log',
    level=logging.DEBUG,
)

app = flask.Flask(__name__)
app.config['SECRET_KEY'] = ''.join(random.choice(HASH_STRING) for _ in xrange(48))
socketio = flask_socketio.SocketIO(app)


def count_hash(url):
    return hashlib.sha256(url).hexdigest()


def shorten(url):
    my_domain = 'http://{}/{}'
    hash_url = count_hash(url)
    short_url, _ = etcd.get('/hash_url/short_url/{}'.format(hash_url))

    if short_url is None:
        transaction_status = False
        while not transaction_status:
            short_url = ''.join(random.choice(HASH_STRING) for _ in xrange(random.randint(4, 8)))

            transaction_status, responses = etcd.transaction(
                compare=[
                    etcd.transactions.version('/hash_url/short_url/{}'.format(hash_url)) == 0,
                    etcd.transactions.version('/short_url/long_url/{}'.format(short_url)) == 0,
                ],
                success=[
                    etcd.transactions.put('/hash_url/short_url/{}'.format(hash_url), short_url),
                    etcd.transactions.put('/short_url/long_url/{}'.format(short_url), url),
                ],
                failure=[
                    etcd.transactions.get('/hash_url/short_url/{}'.format(hash_url)),
                    etcd.transactions.get('/short_url/long_url/{}'.format(short_url)),
                ]
            )

            if not transaction_status:
                logging.exception(
                    '{msg0}: False;\n{msg1}: {h_url}={s_url1};\n{msg2}: {s_url2}={l_url}'.format(
                        msg0='transaction status',
                        msg1='hash_url=>short_url kv entry',
                        h_url=hash_url,
                        s_url1=responses[0],
                        msg2='short_url=>long_url kv entry',
                        s_url2=short_url,
                        l_url=responses[1],
                    )
                )

    return my_domain.format(FQDN, short_url)


def unshorten(path):
    long_url, _ = etcd.get('/short_url/long_url/{}'.format(path))

    return False if long_url is None else long_url


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

    if not SHORT_URL_RE.match(short_url):
        return 'Unknown URL format'

    full_url = unshorten(path=short_url)
    if not full_url:
        return 'Sorry, unknown URL'

    return flask.redirect(location=full_url)


if __name__ == '__main__':
    socketio.run(app)
