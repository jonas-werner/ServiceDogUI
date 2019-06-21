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
import requests
from flask import Flask, jsonify, render_template, redirect, request, url_for, make_response, session
import flask
from werkzeug import secure_filename
from PIL import Image, ImageOps
#import hashlib
import json
from boto.s3.connection import S3Connection
from boto.s3.key import Key
from werkzeug import secure_filename
from pymongo import MongoClient
import pymongo
import qrcode

## Let's throw in a Redis database to generate a unique ID for dogs
## We can use it also to create unique ID's for handlers, documents, photos, QRcodes, cookies ...
# if 'VCAP_SERVICES' in os.environ:
    # VCAP_SERVICES = json.loads(os.environ['VCAP_SERVICES'])
    # CREDENTIALS = VCAP_SERVICES["rediscloud"][0]["credentials"]
    # r = redis.Redis(host=CREDENTIALS["hostname"], port=CREDENTIALS["port"], password=CREDENTIALS["password"])

# else:
    # r = redis.Redis(host='127.0.0.1', port='6379')
    # DB_ENDPOINT = MongoClient('127.0.0.1:27017')
    # DB_NAME = "dogs"
    # global db
    # db = DB_ENDPOINT[DB_NAME]

## Declare environment variables
ecs_access_key_id = os.environ['ECS_access_key']
ecs_secret_key = os.environ['ECS_secret']
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
    #m3api_server= "http://vk-m3engine.cfapps.io"
    #handlerapi_server = "http://handlers.cfapps.io"
    #handler_api = "http://handlerservice.cfapps.io"
    #dog_api = "http://dogservice.cfapps.io"
    handler_api = os.environ['HANDLER_API']
    dog_api = os.environ['DOG_API']
    ui_url=os.environ['UI_URL']

else:
    m3api_server = "http://127.0.0.1:5020"
    handlerapi_server = "http://127.0.0.1:5000"

# print("workflow engine: %s" % m3api_server)
# print("handlerapi_server: %s" % handlerapi_server)

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

############################
# Admin Menu - All Options #
############################
@app.route('/admin')
def admin():

    resp = make_response(render_template('admin.html'))
    return resp

######################
# Dog-related routes #
######################

### Menu of dog available actions
@app.route('/dogs')
def dogs():
    # global userstatus
    resp = make_response(render_template('dogs.html', userstatus=userstatus))
    return resp

@app.route('/searchdog') # search page which submits to viewdog
def searchdog():
    resp = make_response(render_template('searchdog.html', viewdog="viewdog"))
    return resp

@app.route('/searchdogresults', methods=['POST']) # displays result of dog ID search in searchdog
def searchdogresults():

    criteria = request.form['criteria']
    match = request.form['match'].lower()
    print "Searching for {} = {}".format(criteria.lower(), match.lower())
    # Convert True/False strings to boolean as required by API
    if criteria in ["vacc_status", "reg_status"] and match in ["true", "false"]:
        match = str2bool(match)
    if criteria == "handler_id" and match == "none":
        match = None
        print type(match)
    payload = {criteria : match}
    print payload
    url = dog_api + "/api/v1.0/search"
    response = requests.put(url, json=payload)
    dict_resp = json.loads(response.content)
    # print dict_resp
    # print dict_resp["dogs"]

    resp = make_response(render_template('searchdogresults.html', results=dict_resp["dogs"]))
    return resp

### Search for a dog by providing its unique ID
@app.route('/dogbyid') # search page which submits to viewdog
def dogbyid():
    resp = make_response(render_template('dogbyid.html'))
    return resp

### View full dog details by providing its unique ID
@app.route('/viewdog')
def viewdog():

    global username
    userid = "admin"

    dogid = request.args.get('dogid')
    url = dog_api + "/api/v1.0/dog/" + dogid
    response = requests.get(url)
    dict_resp = json.loads(response.content)

    photo = "http://" + namespace + ".public.ecstestdrive.com/" + bname + "/" + dogid + ".jpg"
    qrcode = "http://" + namespace + ".public.ecstestdrive.com/" + bname + "/" + dogid + "-qr.jpg"

    resp = make_response(render_template('viewdog.html', dogid=dogid, dog_details=dict_resp["dog"], photo=photo, qrcode=qrcode))
    return resp

def str2bool(v):
    return v.lower() in ("true")

### Add dog functions: GET and POST
@app.route('/adddog')
def adddog():
    resp = make_response(render_template('newdog.html'))
    return resp

@app.route('/adddogprocess.html', methods=['POST'])
def adddogprocess():

    dog_details = request.form.to_dict()
    # The value of radio buttons are returned as strings. The API expects them in Bool
    dog_details["reg_status"] = str2bool(dog_details["reg_status"])
    dog_details["vacc_status"] = str2bool(dog_details["vacc_status"])
    print dog_details

    # Call the dog service to insert it and get a dogid back
    url = dog_api + "/api/v1.0/dog"
    api_resp = requests.post(url, json=dog_details)
    print api_resp.content
    dict_resp = json.loads(api_resp.content)
    dogid = dict_resp["dog"]["id"]

    ## Now we can upload the photo with a name based on dogid
    myfile = request.files['file']
    # First get the file name and see if it's secure
    if myfile and allowed_file(myfile.filename):
        upload_file(myfile, dogid + ".jpg")
    # This is how will be reached
    photo = "http://" + namespace + ".public.ecstestdrive.com/" + bname + "/" + dogid + ".jpg"

    # Create the QRcode and upload to ECS
    upload_file(qrgen(dogid), dogid + "-qr.jpg")
    qrcode = "http://" + namespace + ".public.ecstestdrive.com/" + bname + "/" + dogid + "-qr.jpg"

    resp = make_response(render_template('dogregistered.html', dogid=dogid, dog_details=dog_details, photo=photo, qrcode=qrcode))
    return resp

### Delete dog: GET and POST
@app.route('/deldog')
def deldog():
    resp = make_response(render_template('deldog.html'))
    return resp

@app.route('/deldogprocess.html', methods=['POST'])
def deldogprocess():

    dogid = request.form['dogid']
    ## We should do an API call to read dog details, display them and ask for confirmation
    ## ... but for now let's keep it simple. We will proceed with the deletion, right away
    url = dog_api + "/api/v1.0/dog/" + dogid
    api_resp = requests.delete(url)

    resp = make_response(render_template('dogdeleted.html', dogid=dogid))
    return resp

### Edit dog. It's a 3 step workflow:
#   1 - What dog you want edit (GET)
#   2 - This is the current information (POST)
#   3 - Let me save it for you (POST)
@app.route('/editdog')
def editdog():
    dogid = ""
    dogid = request.args.get('dogid')
    resp = make_response(render_template('editdog.html', dogid=dogid))
    return resp

@app.route('/editdogshowcurrent.html', methods=['GET','POST'])
def editdogshowcurrent():

    ### This is a Work-in-progress
    # Trying to create another entrypoint to edit dog directly from viewdog pages
    # if request.method == 'GET':
    #     dogid = request.args.get['dogid']


    if request.method == 'POST':
        dogid = request.form['dogid']

    ## Now we call the dog service to read the details of that dog
    url = dog_api + "/api/v1.0/dog/" + dogid
    api_resp = requests.get(url)
    dict_resp = json.loads(api_resp.content)
    # The response is formatted as { "dog" : {"name":"Rufus"}, {},...}
    dog_to_edit = dict_resp["dog"]
    print dog_to_edit
    photo = "http://" + namespace + ".public.ecstestdrive.com/" + bname + "/" + dogid + ".jpg"

    resp = make_response(render_template('currentdog.html', dogid=dogid, dog_details=dog_to_edit, photo=photo))
    return resp

@app.route('/editdogapplychanges.html', methods=['POST'])
def editdogapplychanges():

    dog_details = request.form.to_dict()
    # The value of radio buttons are returned as strings. The API expects them in Bool
    dog_details["reg_status"] = str2bool(dog_details["reg_status"])
    dog_details["vacc_status"] = str2bool(dog_details["vacc_status"])
    # print dog_details
    print("DOG DETAILS: %s" % dog_details)

    # Call the dog service to insert it and get a dogid back
    dogid = request.form['dogid']
    url = dog_api + "/api/v1.0/dog/" + dogid
    api_resp = requests.put(url, json=dog_details)
    dict_resp = json.loads(api_resp.content)
    print dict_resp["dog"]

    ## Let's upload the photo
    myfile = request.files['file']
    print "The file is: "
    print myfile
    # First get the file name and see if it's secure
    if myfile and allowed_file(myfile.filename):
        upload_file(myfile, dogid + ".jpg")

    photo = "http://" + namespace + ".public.ecstestdrive.com/" + bname + "/" + dogid + ".jpg"

    resp = make_response(render_template('dogmodified.html', dogid=dogid, dog_details=dict_resp["dog"], photo=photo))
    return resp

##########################
# Handler-related routes #
##########################

### Menu of handler available actions
@app.route('/handlers')
def handlers():
    # global userstatus
    resp = make_response(render_template('handlers.html', userstatus=userstatus))
    return resp

@app.route('/handlerbyid') # search page which submits to viewhandler
def handlerbyid():
    resp = make_response(render_template('handlerbyid.html'))
    return resp

@app.route('/searchhandler') # search page which submits to viewhandler
def searchhandler():
    # resp = make_response(render_template('searchhandler.html', viewhandler="viewhandler"))
    resp = make_response(render_template('searchhandler.html'))
    return resp

@app.route('/searchhandlerresults', methods=['POST'])
def searchhandlerresults():

    criteria = request.form['criteria']
    match = request.form['match'].lower()
    print "Searching for {} = {}".format(criteria.lower(), match.lower())
    # Convert True/False strings to boolean as required by API
    payload = {criteria : match}
    # print payload
    url = handler_api + "/api/v1.0/search"
    response = requests.put(url, json=payload)
    dict_resp = json.loads(response.content)
    # print dict_resp
    # print dict_resp["dogs"]

    resp = make_response(render_template('searchhandlerresults.html', results=dict_resp["handlers"]))
    return resp

# displays result of Handler ID search in searchhandler
@app.route('/viewhandler')
def viewhandler():

    h_id = request.args.get('h_id')
    url = handler_api + "/api/v1.0/handler/" + h_id

    response = requests.get(url)
    dict_resp = json.loads(response.content)
    print dict_resp["handler"]

    resp = make_response(render_template('viewhandler.html', handlerinfo=dict_resp["handler"], h_id=h_id))
    return resp

### Add dog functions: GET and POST
@app.route('/addhandler')
def addhandler():
    resp = make_response(render_template('newhandler.html'))
    return resp

@app.route('/addhandlerprocess.html', methods=['POST'])
def addhandlerprocess():

    handler_details = request.form.to_dict()
    print handler_details

    # Call the dog service to insert it and get a dogid back
    url = handler_api + "/api/v1.0/handler"
    api_resp = requests.post(url, json=handler_details)
    dict_resp = json.loads(api_resp.content)
    h_id = dict_resp["handler"]["id"]

    resp = make_response(render_template('handlerregistered.html', h_id=h_id, handler_details=handler_details))
    return resp

### Delete dog: GET and POST
@app.route('/delhandler')
def delhandler():
    resp = make_response(render_template('delhandler.html'))
    return resp

@app.route('/delhandlerprocess.html', methods=['POST'])
def delhandlerprocess():

    i = request.form['h_id']
    ## We should do an API call to read dog details, display them and ask for confirmation
    ## ... but for now let's keep it simple. We will proceed with the deletion, right away
    url = handler_api + "/api/v1.0/handler/" + i
    api_resp = requests.delete(url)

    resp = make_response(render_template('handlerdeleted.html', h_id=h_id))
    return resp

## Registration page that submits a form to hregistrationaction
# @app.route('/registerhandler', methods=['GET','POST'])
# def registerhandler():
#     global uuid
#     # Let's create a unique handler ID
#     handler_counter = r.incr('counter_dog')
#     print "the handler counter is now: ", handler_counter
#     ## Create a new key that with the counter and pad with leading zeroes
#     ## d00001, d00002, ... We could use h00001 and so on for handlers
#     newhandler = 'h' + str(handler_counter).zfill(5)
#     print newhandler
#     resp = make_response(render_template('registerhandler.html', hregistrationaction="hregistrationaction", uuid=uuid, newhandler=newhandler))
#     return resp

# @app.route('/hregistrationaction', methods=['POST']) # displays result of handler registration
# def hregistrationaction():

#     outstring = ""
#     allvalues = request.form
# ##    print allvalues
#     h_id = request.form['h_id']
# ##    print ("h_id requested for creation: %s" % h_id)
#     m3api_uri = "/api/v1/handler/add"

#     url = (m3api_server+m3api_uri)

#     m3api_response = requests.post(url, data=allvalues)
# ##    print ("m3engine response: %s" % m3api_response)

#     if m3api_response:
#         m3api_status = {'Result': 'Handler Add from UI - SUCCESS'}
#     else:
#         m3api_status = {'Result': 'Handler Add from UI - FAIL'}
# ##    print m3api_status

#     resp = make_response(render_template('registeredhandler.html', h_id=h_id, status=m3api_status))

#     return resp

##################################
# External verification function #
# Intended for Service Providers #
##################################

@app.route('/verify/<dogid>', methods=["GET"])
def verify(dogid):
    # Get the dogid from the URL and call the dogs service
    url = dog_api + "/api/v1.0/dog/" + dogid
    dog_response = requests.get(url)

    # Extract dog details from response and get the id of its handler
    dog_dict = json.loads(dog_response.content)
    #print dog_dict["h_id"]

    # We can pull the details for the handler now
    url = handler_api + "/api/v1.0/handler/" + dog_dict["dog"]["handler_id"]
    handler_response = requests.get(url)

    # Extract handler details
    handler_dict = json.loads(handler_response.content)

    # Select data to be presented
    #print dog_dict["dog"]["name"]
    #print dog_dict["dog"]["pedigree"]
    #print "we will use " + dogid + " to pull the photo from ECS "
    #print handler_dict["handler"]["first_name"]
    # print "we can use " + dog_dict["dog"]["handler_id"] + " to pull the photo from ECS "
    dog_photo = "http://" + namespace + ".public.ecstestdrive.com/" + bname + "/" + dogid + ".jpg"
    handler_name = handler_dict["handler"]["first_name"] + " " + handler_dict["handler"]["last_name"]

    resp = make_response(render_template('verify.html', name=dog_dict["dog"]["name"],\
                    pedigree=dog_dict["dog"]["pedigree"], registration_id=dog_dict["dog"]["registration_id"],\
                    handler_name=handler_name, dog_photo=dog_photo))
    return resp

## This is the API version, to allow PetCo to print badges
## If we add an API gateway it should be expose there instead
@app.route('/api/v1/verify/<dogid>', methods=["GET"])
def apiverify(dogid):
    # Get the dogid from the URL and call the dogs service
    url = dog_api + "/api/v1.0/dog/" + dogid
    dog_response = requests.get(url)

    # Extract dog details from response and get the id of its handler
    dog_dict = json.loads(dog_response.content)
    print dog_dict

    # We can pull the details for the handler now
    url = handler_api + "/api/v1.0/handler/" + dog_dict["dog"]["handler_id"]
    handler_response = requests.get(url)

    # Extract handler details
    handler_dict = json.loads(handler_response.content)

    dog_photo = "http://" + namespace + ".public.ecstestdrive.com/" + bname + "/" + dogid + ".jpg"
    handler_name = handler_dict["handler"]["first_name"] + " " + handler_dict["handler"]["last_name"]

    payload = {
        "name" : dog_dict["dog"]["name"],
        "pedigree" : dog_dict["dog"]["pedigree"],
        "handler_name" : handler_name,
        "dog_photo" : dog_photo,
        "registration_id" : dog_dict["dog"]["registration_id"]
    }
    return jsonify( { 'dog': payload } )


############################
# ECS and QRcode functions #
############################

def upload_file(myfile, fname):
    # Save it locally to the "/uploads" directory. Don't forget to create the DIR !!!
    myfile.save(os.path.join("uploads", fname))
    # Now let's upload it to ECS
    print "Uploading " + fname + " to ECS"
    k = b.new_key(fname)
    k.set_contents_from_filename("uploads/" + fname)
    k.set_acl('public-read')
    # Finally remove the file from our container. We don't want to fill it up ;-)
    os.remove("uploads/" + fname)
    return

def qrgen(dogid):
    URL = ui_url + "/verify/" + dogid
    img = qrcode.make(URL)
    return img

##################
# Error Handlers #
##################
# @app.errorhandler(404)
# def page_not_found(e):
#     ''' Display the page no found message '''
#     return render_template('404.html'), 400

# @app.errorhandler(500)
# def internal_server_error(e):
#     ''' Display the server error message '''
#     return render_template('500.html'), 500

###############################
## Status APIs health-checks ##
###############################
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

@app.route('/uid')
def uid():
    uuid = request.cookies.get('uuid')
    return "Your user ID is : " + uuid

if __name__ == "__main__":
	app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', '5000')), threaded=True)
