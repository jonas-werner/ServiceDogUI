# 2019-06-06
# ServiceDogUI (User Interface)
# Version 0.xxxxx
# Written by Grant, Veronique, Jonas
## Change line to trigger Jenkins build


import uuid
import time
import os, sys
import re
import boto
import redis
import requests
from flask import Flask, jsonify, render_template, redirect, request, url_for, make_response, session
import flask
from werkzeug import secure_filename
from PIL import Image, ImageOps
#import hashlib
import json
from UploadForm import UploadForm
from boto.s3.connection import S3Connection
from boto.s3.key import Key

# declare environment variables
ecs_endpoint = os.getenv('ecs_endpoint')
ecs_access_key = os.getenv('ecs_access_key')
ecs_secret_key = os.getenv('ecs_secret_key')
ecs_bucket_name = os.getenv('ecs_bucket_name')
fileuuid = uuid.uuid4()

global dogsname
dogsname = ''
global handlersname
handlersname = ''

app = Flask(__name__)

## Identify where we're running
if 'VCAP_SERVICES' in os.environ:
##    m3api_server = "http://servicedogwfe.cfapps.io"
    m3api_server= "http://vk-m3engine.cfapps.io"
else:
    m3api_server = "http://127.0.0.1:5020"

print("workflow engine: %s" % m3api_server)


my_uuid = str(uuid.uuid1())
username = ""
userstatus = "0"
# uuid = "0"

@app.route('/')
def menu():

    current = int(time.time())-time.timezone
    global userstatus
    # global uuid
    # global my_uuid

    # print("UUID STRING: %s" % my_uuid)

    uuid = request.cookies.get('uuid')
    if uuid and not uuid == "0":
        userstatus = "1"
    else:
        userstatus = "0"


    resp = make_response(render_template('main_menu.html', userstatus=userstatus, uuid=uuid))

    return resp

@app.route('/loginform', methods=['GET','POST'])
def loginform():

    global uuid
    global username
    global userstatus

    uuid        = request.cookies.get('uuid')


    if request.method == 'POST':

        username    = request.form['username']
        password    = request.form['password']


    if not uuid:
        # No UUID, the user need to authenticate OR the user credentials were invalid
        print "uuid cookie was not present"

        if request.method == 'GET':
            # First time user accesses page. Show login form
            resp = make_response(render_template('loginform.html', login="loginform", status=""))

        else:
            # Method is POST. User is trying to authenticate
            # url = 'http://localhost:5010/api/v1/auth'

            # url = 'http://servicedogauth.cfapps.io:5010/api/v1/auth'
            # payload = {"username": username,"password":password}
            # headers = {'content-type': 'application/json'}
            #
            # response = requests.post(url, payload).text
            # response = json.loads(response)
            #
            # userstatus  = response['userstatus']
            # userrole    = response['userrole']

            userstatus  = "1"
            userrole    = "administrator"


            if userstatus == "1":
                # User login successful
                resp = make_response(render_template('logincomplete.html', uuid=my_uuid))
                resp.set_cookie('uuid',str(my_uuid), max_age=1800)

            elif userstatus == "0":
                # User has a failed login
                resp = make_response(render_template('loginform.html', login="loginform", status="Username or password was incorrect. Please try again."))
    else:
        resp = make_response(render_template('logincomplete.html', uuid=my_uuid))
        resp.set_cookie('uuid',str(my_uuid), max_age=1800)

    return resp


@app.route('/logout', methods=['GET','POST'])
def logout():
    global uuid

    uuid = request.cookies.get('uuid')

    if not uuid:
        # No UUID, the user need to authenticate OR the user credentials were invalid
        print "User trying to log out but is not logged in."
        resp = make_response(render_template('logoutform.html', status="Session not active. No need to log out."))

    else:
        resp = make_response(render_template('logoutform.html', status="Your session has been closed."))
        resp.set_cookie('uuid',str(my_uuid), max_age=0)

    return resp



@app.route('/dogs')
def dogs():
    # global userstatus
    resp = make_response(render_template('dogs.html', userstatus=userstatus))
    return resp

@app.route('/searchdog') # search page which submits to viewdog
def searchdog():
    resp = make_response(render_template('searchdog.html', viewdog="viewdog"))
    return resp

@app.route('/viewdog', methods=['POST']) # displays result of dog ID search in searchdog
def viewdog():

    global username

    outstring = ""
    allvalues = sorted(request.form.items())
    for key,value in allvalues:
        outstring += key + ":" + value + ";"
    print outstring


    userid = "admin"
    sd_regid = request.form['dogid']

    url = 'http://servicedogwfe.cfapps.io/api/v1/dog/view'

    # payload = {"userid": username,"sd_regid":sd_regid}
    payload = {"userid": userid,"sd_regid":sd_regid}

    # response = requests.post(url, payload).text
    response = requests.get(url, params=payload)
    print("RESPONSE: %s" % response)

    whatever = json.loads(response.content)
    # print whatever["sd_regid"]
    # print whatever["sd_name"]

    # response = allvalues

    resp = make_response(render_template('viewdog.html', doginfo=whatever))

    return resp


@app.route('/registerdog', methods=['GET','POST'])
def registerdog():
# ''' Read the root document and load form '''
    file = None
    form = UploadForm()
    if form.validate_on_submit():  # If form is valid store info in a session
        session['endpoint'] = ecs_endpoint
        session['access_key'] = ecs_access_key
        session['secret_key'] = ecs_secret_key
        session['bucket_name'] = ecs_bucket_name
        session['dogsname'] = form.dogsname.data
        session['handlersname'] = form.handlersname.data
        url = ecs_upload(ecs_bucket_name, form)  # Upload object to ECS
        session['signed_url'] = url
        dogsname = str(form.dogsname.data)
        handlersname = str(form.handlersname.data)
        print "the dogs name is: " + dogsname
        print "the handlers name is " + handlersname
        return redirect(url_for('uploaded'))  # Once file is uploaded redirect to completed page
    return render_template('index.html',
                           form=form,
                           endpoint=session.get(ecs_endpoint),
                           access_key=session.get(ecs_access_key),
                           secret_key=session.get(ecs_secret_key),
                           bucket_name=session.get(ecs_bucket_name),
                           file=file)


def ecs_upload(ecs_bucket_name, form):
# ''' Upload the file to the ECS storage '''

    filenameprefix = str(fileuuid) + " - "
    filename = filenameprefix + secure_filename(form.file.data.filename)  # make sure the filename pass is safe
    conn = S3Connection(aws_access_key_id=session['access_key'],
                        aws_secret_access_key=session['secret_key'],
                        host=session['endpoint'])
    bucket_name = session['bucket_name']
    is_bucket_present = conn.lookup(bucket_name)  # check if there is an existing bucket with the same name
    if is_bucket_present is None:  # if there are no buckets, create one
        conn.create_bucket(bucket_name)
    bucket = conn.get_bucket(bucket_name)  # get the bucket
    k = Key(bucket)  # get an object key for it

    k.key = filename
    k.set_contents_from_file(form.file.data)  # store the content in ECS
    expire_time = int(app.config['EXPIRE_TIME'])
    url = conn.generate_url(expires_in=expire_time,
                            method='GET',
                            bucket=bucket_name,
                            key=k.key)

    print dogsname
    # placeholder for finding a way to set metadata tags using set_metadata

    return url



@app.route('/uploaded', methods=['GET'])
def uploaded():
# ''' Display a page with the link to the uploaded object '''
    sign_url = session['signed_url']
    return render_template('uploaded.html', sign_url=sign_url, expire_at=app.config['EXPIRE_TIME'])


@app.errorhandler(404)
def page_not_found(e):
    ''' Display the page no found message '''
    return render_template('404.html'), 400


@app.errorhandler(500)
def internal_server_error(e):
    ''' Display the server error message '''
    return render_template('500.html'), 500





@app.route('/handlers')
def handlers():
    # global userstatus
    resp = make_response(render_template('handlers.html', userstatus=userstatus))
    return resp


@app.route('/searchhandler') # search page which submits to viewhandler
def searchhandler():
    resp = make_response(render_template('searchhandler.html', viewhandler="viewhandler"))
    return resp



@app.route('/viewhandler', methods=['POST']) # displays result of Handler ID search in searchhandler
def viewhandler():

    global username

    outstring = ""
    allvalues = sorted(request.form.items())
    for key,value in allvalues:
        outstring += key + ":" + value + ";"
    print outstring


    userid = "admin"
    h_id = request.form['handlerid']

    m3api_uri = "/api/v1/handler/view"
    url = (m3api_server+m3api_uri)

    # payload = {"userid": username,"sd_regid":sd_regid}
    payload = {"userid": userid,"h_id": h_id}

    # response = requests.post(url, payload).text
    m3api_response = requests.get(url, params=payload)
    print("RESPONSE: %s" % m3api_response)

    whatever = json.loads(m3api_response.content)
    # print whatever["sd_regid"]
    # print whatever["sd_name"]

    # response = allvalues

    resp = make_response(render_template('viewhandler.html', handlerinfo=whatever))

    return resp

## Registration page that submits a form to hregistrationaction
@app.route('/registerhandler', methods=['GET','POST'])
def registerhandler():
    global uuid
    resp = make_response(render_template('registerhandler.html', hregistrationaction="hregistrationaction", uuid=uuid))
    return resp

@app.route('/hregistrationaction', methods=['POST']) # displays result of handler registration
def hregistrationaction():

    outstring = ""
    allvalues = request.form
##    print allvalues
    h_id = request.form['h_id']
##    print ("h_id requested for creation: %s" % h_id)
    m3api_uri = "/api/v1/handler/add"

    url = (m3api_server+m3api_uri)

##    ## Upload pic to S3
##    s3_access_key_id    = ''
##    s3_secret_key       = ''
##
##    session = boto.connect_s3(s3_access_key_id, s3_secret_key, host='s3.us-east-1.amazonaws.com')
##
##    bname = 'jwr-piedpiper-01'
##    b = session.get_bucket(bname)
##
##    k = b.new_key(dogpic)
##    k.set_metadata('dogid', dogid)
##    k.set_contents_from_filename(dogpic)
##    k.set_acl('public-read')
##    ## End Upload pic to S3
##
##    ## Do we need to reformat h_picture field before passing it on?
##    ## h_picture should be a URI to Handler's picture in the S3 bucket

    m3api_response = requests.post(url, data=allvalues)
##    print ("m3engine response: %s" % m3api_response)

    if m3api_response:
        m3api_status = {'Result': 'Handler Add from UI - SUCCESS'}
    else:
        m3api_status = {'Result': 'Handler Add from UI - FAIL'}
##    print m3api_status

    resp = make_response(render_template('registeredhandler.html', h_id=h_id, status=m3api_status))

    return resp

@app.route('/uid')
def uid():
    uuid = request.cookies.get('uuid')
    return "Your user ID is : " + uuid

if __name__ == "__main__":
	app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', '5030')), threaded=True)
