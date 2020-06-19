"""
This file defines actions, i.e. functions the URLs are mapped into
The @action(path) decorator exposed the function at URL:

    http://127.0.0.1:8000/{app_name}/{path}

If app_name == '_default' then simply

    http://127.0.0.1:8000/{path}

If path == 'index' it can be omitted:

    http://127.0.0.1:8000/

The path follows the bottlepy syntax.

@action.uses('generic.html')  indicates that the action uses the generic.html template
@action.uses(session)         indicates that the action uses the session
@action.uses(db)              indicates that the action uses the db
@action.uses(T)               indicates that the action uses the i18n & pluralization
@action.uses(auth.user)       indicates that the action requires a logged in user
@action.uses(auth)            indicates that the action requires the auth object

session, db, T, auth, and tempates are examples of Fixtures.
Warning: Fixtures MUST be declared with @action.uses({fixtures}) else your app will result in undefined behavior
"""

import uuid

from py4web import action, request, abort, redirect, URL, Field
from py4web.utils.form import Form, FormStyleBulma
from py4web.utils.url_signer import URLSigner

from yatl.helpers import A
from . common import db, session, T, cache, auth, signed_url


url_signer = URLSigner(session)


def _get_phone_numbers_string(contact_id):
    phones_str = ''
    phones = db(db.phone.contact_id == contact_id).select()
    for phone in phones:
        if phones_str:
            phones_str += ', '
        phones_str += f'{phone.number} ({phone.name})'
    return phones_str


# The auth.user below forces login.
@action('index')
@action.uses('index.html', auth.user, db, url_signer)
def index():
    user_email = auth.current_user.get('email')
    contacts = db(db.contact.user_email == user_email).select().as_list()
    for contact in contacts:
        contact['phones_str'] = _get_phone_numbers_string(contact['id'])
    return dict(contacts=contacts, url_signer=url_signer)


@action('add_contact', method=['GET', 'POST'])
@action.uses('contact_form.html', auth.user, db, session)
def add_contact():
    form = Form(db.contact, csrf_session=session, formstyle=FormStyleBulma)
    if form.accepted:
        # We always want POST requests to be redirected as GETs.
        redirect(URL('index'))
    return dict(form=form)


@action('edit_contact/<contact_id>', method=['GET', 'POST'])
@action.uses('contact_form.html', auth.user, db, session)
def edit_contact(contact_id=None):
    """Note that in the above declaration, the contact_id argument must match
    the <contact_id> argument of the @action."""
    # We read the contact.
    c = db.contact[contact_id]
    user_email = auth.current_user.get('email')
    if c is None or c.user_email != user_email:
        # Nothing to edit or wrong user
        redirect(URL('index'))
    form = Form(db.contact, record=c, deletable=False, csrf_session=session, formstyle=FormStyleBulma)
    if form.accepted:
        # We always want POST requests to be redirected as GETs.
        redirect(URL('index'))
    return dict(form=form)


@action('delete_contact/<contact_id>')
@action.uses(auth.user, db, session, url_signer.verify())
def delete_contact(contact_id=None):
    # We read the contact.
    c = db.contact[contact_id]
    user_email = auth.current_user.get('email')
    if c is not None and c.user_email == user_email:
        # Only delete if contact exists
        del db.contact[contact_id]
    # Always redirect, regardless of whether contact actually existed or not
    redirect(URL('index'))


@action('phone_numbers/<contact_id>', method=['GET', 'POST'])
@action.uses('phone_numbers.html', auth.user, db, session, url_signer)
def phone_numbers(contact_id=None):
    """Note that in the above declaration, the contact_id argument must match
    the <contact_id> argument of the @action."""
    # We read the contact.
    c = db.contact[contact_id]
    user_email = auth.current_user.get('email')
    if c is None or c.user_email != user_email:
        # No contact or wrong user
        redirect(URL('index'))

    phones = db(db.phone.contact_id == contact_id).select()
    contact = f'{c.first_name} {c.last_name}'
    return dict(contact_id=contact_id, contact=contact, phones=phones, url_signer=url_signer)


@action('add_phone/<contact_id>', method=['GET', 'POST'])
@action.uses('phone_form.html', auth.user, db, session)
def add_phone(contact_id=None):
    # We read the contact.
    c = db.contact[contact_id]
    user_email = auth.current_user.get('email')
    if c is None or c.user_email != user_email:
        # Contact does not exist or wrong user
        redirect(URL('index'))

    form = Form([Field('number'), Field('name')], csrf_session=session, formstyle=FormStyleBulma)
    if form.accepted:
        # Create phone and insert into table
        db.phone.insert(name=form.vars['name'], number=form.vars['number'], contact_id=contact_id)
        db.commit()
        # We always want POST requests to be redirected as GETs.
        redirect(URL('phone_numbers', contact_id))
    return dict(contact_id=contact_id, form=form)


@action('edit_phone/<phone_id>', method=['GET', 'POST'])
@action.uses('phone_form.html', auth.user, db, session)
def edit_phone(phone_id=None):
    # """Note that in the above declaration, the contact_id argument must match
    # the <contact_id> argument of the @action."""
    # # We read the contact.
    p = db.phone[phone_id]
    if p is None:
        redirect(URL('index'))

    c = db.contact[p.contact_id]
    user_email = auth.current_user.get('email')
    if c.user_email != user_email:
        redirect(URL('index'))

    # Only display form if phone exists and contact belongs to logged in user
    form = Form([Field('number'), Field('name')],
                record=dict(name=p.name, number=p.number),
                csrf_session=session,
                formstyle=FormStyleBulma)
    if form.accepted:
        # Create phone and insert into table
        db.phone[phone_id] = dict(number=form.vars['number'], name=form.vars['name'])
        db.commit()
        redirect(URL('phone_numbers', c.id))
    return dict(contact_id=c.id, form=form)


@action('delete_phone/<phone_id>')
@action.uses(auth.user, db, session, url_signer.verify())
def delete_phone(phone_id=None):
    # We read the phone and corresponding contact (if phone exists).
    p = db.phone[phone_id]
    if p is None:
        redirect(URL('index'))

    c = db.contact[p.contact_id]
    user_email = auth.current_user.get('email')
    if c.user_email == user_email:
        # Only delete if phone exists and contact belongs to logged in user
        del db.phone[phone_id]
        redirect(URL('phone_numbers', c.id))
    redirect(URL('index'))
