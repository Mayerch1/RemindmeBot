import discord
import logging
import graypy


cl_logger = None
logger = None


def init_loggers():
    global cl_logger
    global logger

    cl_logger = logging.getLogger('discord')
    cl_logger.setLevel(logging.INFO)
    handler = logging.FileHandler(filename='./discord.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    cl_logger.addHandler(handler)

    logger = logging.getLogger('gray_logger')
    logger.setLevel(logging.DEBUG)

    gray_handler = graypy.GELFUDPHandler('graylog', 12201)
    logger.addHandler(gray_handler)