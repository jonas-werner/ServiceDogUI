from flask_wtf import Form
from wtforms import SubmitField, StringField, FileField
from wtforms.validators import DataRequired

class UploadForm(Form):
    '''This is the input form to display'''
    dogsname = StringField('Dogs Name', validators=[DataRequired()])
    handlersname = StringField('Handlers Full Name', validators=[DataRequired()])
    file = FileField('Supply Dogs Photograph', validators=[DataRequired()])
    submit = SubmitField('Upload')


