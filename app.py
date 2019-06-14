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
from werkzeug import secure_filename
from pymongo import MongoClient
import pymongo

## Let's throw in a Redis database to generate a unique ID for dogs
## We can use it also to create unique ID's for handlers, documents, photos, QRcodes, cookies ...
if 'VCAP_SERVICES' in os.environ:
    VCAP_SERVICES = json.loads(os.environ['VCAP_SERVICES'])
    # CREDENTIALS = VCAP_SERVICES["rediscloud"][0]["credentials"]
    # r = redis.Redis(host=CREDENTIALS["hostname"], port=CREDENTIALS["port"], password=CREDENTIALS["password"])
    r = redis.Redis(host="<cut from github push>", port="<cut from github push>", password="<cut from github push>")

else:
    r = redis.Redis(host='192.168.2.4', port='6379')
    ## Using local MongoDB for Dev. In real life I will have to do API call to M3engine
    DB_ENDPOINT = MongoClient('192.168.2.4:27017')
    DB_NAME = "dogs"
    global db
    db = DB_ENDPOINT[DB_NAME]


# declare environment variables
# Grant's ECS info
# ecs_endpoint = os.getenv('ecs_endpoint')
# ecs_access_key = os.getenv('ecs_access_key')
# ecs_secret_key = os.getenv('ecs_secret_key')
# ecs_bucket_name = os.getenv('ecs_bucket_name')
# fileuuid = uuid.uuid4()

# Tanzil's ECS info
ecs_access_key_id = '<cut from github push>'
ecs_secret_key = '<cut from github push>'
## We can now extract "namespace" from the access key
namespace = ecs_access_key_id.split('@')[0]

session = boto.connect_s3(ecs_access_key_id, ecs_secret_key, host='object.ecstestdrive.com')
bname = 'dogphotos'
b = session.get_bucket(bname)
print "Bucket is: " + str(b)

app = Flask(__name__)
app.config['ALLOWED_EXTENSIONS'] = set(['jpg', 'jpeg', 'JPG', 'JPEG'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

global dogsname
dogsname = ''
global handlersname
handlersname = ''


## Identify where we're running
# if 'VCAP_SERVICES' in os.environ:
if 1 == 1:
    # m3api_server = "http://servicedogwfe.cfapps.io"
    m3api_server= "http://vk-m3engine.cfapps.io"
    handlerapi_server = "http://handlers.cfapps.io"
else:
    m3api_server = "http://127.0.0.1:5020"
    handlerapi_server = "http://127.0.0.1:5000"

print("workflow engine: %s" % m3api_server)
print("handlerapi_server: %s" % handlerapi_server)

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

#
# @app.route('/registerdog', methods=['GET','POST'])
# def registerdog():
# # ''' Read the root document and load form '''
#     file = None
#     form = UploadForm()
#     if form.validate_on_submit():  # If form is valid store info in a session
#         session['endpoint'] = ecs_endpoint
#         session['access_key'] = ecs_access_key
#         session['secret_key'] = ecs_secret_key
#         session['bucket_name'] = ecs_bucket_name
#         session['dogsname'] = form.dogsname.data
#         session['handlersname'] = form.handlersname.data
#         url = ecs_upload(ecs_bucket_name, form)  # Upload object to ECS
#         session['signed_url'] = url
#         dogsname = str(form.dogsname.data)
#         handlersname = str(form.handlersname.data)
#         print "the dogs name is: " + dogsname
#         print "the handlers name is " + handlersname
#         return redirect(url_for('uploaded'))  # Once file is uploaded redirect to completed page
#     return render_template('index.html',
#                            form=form,
#                            endpoint=session.get(ecs_endpoint),
#                            access_key=session.get(ecs_access_key),
#                            secret_key=session.get(ecs_secret_key),
#                            bucket_name=session.get(ecs_bucket_name),
#                            file=file)


# def ecs_upload(ecs_bucket_name, form):
# # ''' Upload the file to the ECS storage '''
#
#     filenameprefix = str(fileuuid) + " - "
#     filename = filenameprefix + secure_filename(form.file.data.filename)  # make sure the filename pass is safe
#     conn = S3Connection(aws_access_key_id=session['access_key'],
#                         aws_secret_access_key=session['secret_key'],
#                         host=session['endpoint'])
#     bucket_name = session['bucket_name']
#     is_bucket_present = conn.lookup(bucket_name)  # check if there is an existing bucket with the same name
#     if is_bucket_present is None:  # if there are no buckets, create one
#         conn.create_bucket(bucket_name)
#     bucket = conn.get_bucket(bucket_name)  # get the bucket
#     k = Key(bucket)  # get an object key for it
#
#     k.key = filename
#     k.set_contents_from_file(form.file.data)  # store the content in ECS
#     expire_time = int(app.config['EXPIRE_TIME'])
#     url = conn.generate_url(expires_in=expire_time,
#                             method='GET',
#                             bucket=bucket_name,
#                             key=k.key)
#
#     print dogsname
#     # placeholder for finding a way to set metadata tags using set_metadata
#
#     return url



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


##
## Status APIs to check on all microservice dependencies
##
## Test Handlers status
@app.route('/api/v1/handler/hstatus',methods=["GET"])
def hstatus():
    apiuri = "/api/v1/handler/hstatus"

    handler_status = requests.get(handlerapi_server+apiuri)
    if handler_status:
        response = {'status': "Handlers API returns my ping"}
        code = 200
    else:
        response = {'statuscode': 400}
        code = 400
    return jsonify(response), code

## Test m3engine status
@app.route('/api/v1/handler/m3estatus', methods=["GET"])
def m3estatus():
    apiuri = "/api/v1/handler/m3estatus"

    handler_status = requests.get(m3api_server+apiuri)
    if handler_status:
        response = {'status': "m3engine API returns my ping"}
        code = 200
    else:
        response = {'statuscode': 400}
        code = 400
    return jsonify(response), code

## Test HandlersUI status
@app.route('/api/v1/handler/huistatus', methods=["GET"])
def huistatus():
    response = {'status': "HandlersUI API up and running"}
    statuscode = 200
    return jsonify(response),statuscode
##
## End dependencies test
##

##
## Begin Handlers UI and functions
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
    # Let's create a unique handler ID
    handler_counter = r.incr('counter_dog')
    print "the handler counter is now: ", handler_counter
    ## Create a new key that with the counter and pad with leading zeroes
    ## d00001, d00002, ... We could use h00001 and so on for handlers
    newhandler = 'h' + str(handler_counter).zfill(5)
    print newhandler
    resp = make_response(render_template('registerhandler.html', hregistrationaction="hregistrationaction", uuid=uuid, newhandler=newhandler))
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

# Photo upload section ############################################
    # myfile = request.files['h_picture']
    # print myfile
    # if myfile and allowed_file(myfile.filename):
    #     ## Save it locally to the "/uploads" directory. Don't forget to create the DIR !!!
    #     myfile.save(os.path.join("uploads", h_id))
    #
    #     ## Now let's upload it to ECS
    #     print "Uploading " + h_id + " to ECS"
    #     k = b.new_key(h_id)
    #     k.set_contents_from_filename("uploads/" + h_id)
    #     k.set_acl('public-read')
    #
    #     # Finally remove the file from our container. We don't want to fill it up ;-)
    #     os.remove("uploads/" + h_id)
# /Photo upload section ############################################

    m3api_response = requests.post(url, data=allvalues)
##    print ("m3engine response: %s" % m3api_response)

    if m3api_response:
        m3api_status = {'Result': 'Handler Add from UI - SUCCESS'}
    else:
        m3api_status = {'Result': 'Handler Add from UI - FAIL'}
##    print m3api_status

    resp = make_response(render_template('registeredhandler.html', h_id=h_id, status=m3api_status))

    return resp

# 2019-06-13 - New content from Alberto and Tanzil below:
################################################################3
@app.route('/adddog')
def adddog():
    resp = make_response(render_template('newdog.html'))
    return resp

@app.route('/adddogprocess.html', methods=['POST'])
def adddogprocess():

    n = request.form['dog_name']
    d = request.form['vacc_date']
    s = request.form['vacc_status']
    h = request.form['handler_id']

    # If no Handler ID is specified we mark the dog as FREE
    # This make it easier to implement the search query in MongoDB
    if not h:
        h = "FREE"

    # Let's create a unique dog ID
    dog_counter = r.incr('counter_dog')
    print "the dog counter is now: ", dog_counter
    ## Create a new key that with the counter and pad with leading zeroes
    ## d00001, d00002, ... We could use h00001 and so on for handlers
    newdog = 'd' + str(dog_counter).zfill(5)
    print newdog

    ## Let's upload the photo
    ## First get the file name and see if it's secure
    myfile = request.files['file']
    print myfile
    if myfile and allowed_file(myfile.filename):
        ## Save it locally to the "/uploads" directory. Don't forget to create the DIR !!!
        myfile.save(os.path.join("uploads", newdog))

        ## Now let's upload it to ECS
        print "Uploading " + newdog + " to ECS"
        k = b.new_key(newdog)
        k.set_contents_from_filename("uploads/" + newdog)
        k.set_acl('public-read')

        # Finally remove the file from our container. We don't want to fill it up ;-)
        os.remove("uploads/" + newdog)

    print "Storing the dog now "
    print "Dog Name is " + n
    print "Vaccination date is " + d
    print "Vaccination status " + s
    #### API call to dogs microservice should go here #####
    ## for now let's simulate it with local MongoDB
    db.dogscollection.insert_one({"dogid" : newdog, "name" : n, "vacc_date" : d, "vacc_status" : s, "handler_id" : h})

    ## Finally acknowledge the dog registration

    resp = make_response(render_template('dogregistered.html', newdog=newdog, n=n, d=d, s=s, h=h, namespace=namespace))
    return resp

@app.route('/deldog')
def deldog():
    resp = make_response(render_template('deldog.html'))
    return resp

@app.route('/deldogprocess.html', methods=['POST'])
def deldogprocess():

    id = request.form['dogid']
    ## Now we should perform an API call to read the details of that dog
    ## display them and ask for confirmation
    ## ... but for now let's simplify the workflow. We will proceed with the deletion
    ## This should be a single API call to M3engine, but I will simulate in local MongoDB
    db.dogscollection.delete_one({"dogid" : id})

    return """<h2>Your deletion request has been initiated ... and hopefully processed :-D
    <br><a href="/">Back to main menu</a>"""

@app.route('/editdog')
def editdog():
    resp = make_response(render_template('editdog.html'))
    return resp

@app.route('/editdogshowcurrent.html', methods=['POST'])
def editdogshowcurrent():

    id = request.form['dogid']
    ## Now we should perform an API call to read the details of that dog
    ## but I will simulate in local MongoDB
    dog_to_edit = db.dogscollection.find_one({"dogid" : id})
    name = dog_to_edit["name"]
    vdate = dog_to_edit["vacc_date"]
    vstatus = dog_to_edit["vacc_status"]
    hid = dog_to_edit["handler_id"]
    photo = "http://" + namespace + ".public.ecstestdrive.com/dogphotos/" + id
    print "Current data is:"
    print name, vdate, vstatus, hid

    resp = make_response(render_template('currentdog.html', name=name, vdate=vdate, vstatus=vstatus, photo=id, hid=hid, dogid=id))
    return resp

@app.route('/editdogapplychanges.html', methods=['POST'])
def editdogapplychanges():

    i = request.form['dogid']
    n = request.form['dog_name']
    h = request.form['handler_id']
    d = request.form['vacc_date']
    s = request.form['vacc_status']
    print "We will write these:"
    print i, n, h, d, s

    ## Let's upload the photo
    ## First get the file name and see if it's secure
    myfile = request.files['file']
    print myfile
    if myfile and allowed_file(myfile.filename):
        print "A file was also uploaded"
        ## Save it locally to the "/uploads" directory. Don't forget to create the DIR !!!
        myfile.save(os.path.join("uploads", i))

        ## Now let's upload it to ECS
        print "Uploading " + i + " to ECS"
        k = b.new_key(i)  # The key is the same so it will overwrite the existing photo
        k.set_contents_from_filename("uploads/" + i)
        k.set_acl('public-read')

        # Finally remove the file from our container. We don't want to fill it up ;-)
        os.remove("uploads/" + i)

    db.dogscollection.update_one(
                    {"dogid" : i},
                    {"$set":
                        {"name" : n, "vacc_date" : d, "vacc_status" : s, "handler_id" : h}},
                    upsert=True)


    resp = make_response(render_template('dogregistered.html', newdog=i, n=n, d=d, s=s, h=h, namespace=namespace))

    return resp


@app.route('/uid')
def uid():
    uuid = request.cookies.get('uuid')
    return "Your user ID is : " + uuid

if __name__ == "__main__":
	app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', '5030')), threaded=True)
