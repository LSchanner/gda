# -*- coding: utf-8 -*-
import dac_parser
from models import *
from constants import *

def update_courses():
    LocDB = create_engine(UserDB, echo=False)
    LocS = sessionmaker(bind=LocDB)()
    courses = dac_parser.get_courses()
