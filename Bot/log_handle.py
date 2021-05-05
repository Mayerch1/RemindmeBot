import discord
import logging
import graypy
import os


cl_logger = None
logger = None


graylog_url = os.getenv('GRAYLOG_URL')

def init_loggers():
    global cl_logger
    global logger

    cl_logger = logging.getLogger('discord')
    cl_logger.setLevel(logging.INFO)
    handler = logging.FileHandler(filename='./discord.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    cl_logger.addHandler(handler)

    logger = logging.getLogger('gray_logger')
    logger.setLevel(logging.INFO)

    gray_handler = graypy.GELFUDPHandler(graylog_url, 12201)
    logger.addHandler(gray_handler)