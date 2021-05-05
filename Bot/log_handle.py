import discord
import logging
import graypy
import os

cl_logger = None
logger = None


def init_loggers():
    global cl_logger
    global logger

    cl_logger = logging.getLogger('discord')
    cl_logger.setLevel(logging.INFO)
    cl_handler = logging.FileHandler(filename='./discord.log', encoding='utf-8', mode='w')
    cl_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    cl_logger.addHandler(cl_handler)


    logger = logging.getLogger('reminder')
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(filename='./info.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)