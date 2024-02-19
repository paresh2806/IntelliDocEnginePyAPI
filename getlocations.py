import numpy as np
import geopy
from geopy.geocoders import Nominatim
import psycopg2
from config import config


def getlocations(ARRAY, File_Id):
    location = Nominatim(user_agent="GetLoc")
    params = config()
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    for Temp_location in ARRAY:
        print(Temp_location)
        try:
            getLocation = location.geocode(Temp_location)
            lat = getLocation.latitude
            lon = getLocation.longitude
            cur.execute(f'''insert
            into
            location_geom(latitude, longitude, movement_geom,upload_id)
            values({lat}, {lon}, st_setsrid(st_makepoint({lon},{lat}),4326), {File_Id})''')
            conn.commit()
        except:
            return
