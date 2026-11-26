import os
from utils.general import dict_to_namespace
from dotenv import load_dotenv
load_dotenv()

verParams = {
    "TITLE":"Electronic Monitor API",
    "DESCRIPTION":"Local API for CozyLife Smart Plug monitoring",
    "VERSION":"0.0.3",
}

verParams = dict_to_namespace(verParams)
