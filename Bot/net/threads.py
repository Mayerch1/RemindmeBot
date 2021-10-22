"""this file is implementing underlying thread operations of the discord v9 API
    only necessary calls are implemented and might only supported very specific actions
"""

import os
import requests


token = os.getenv('BOT_TOKEN')


base_url = 'https://discord.com/api/v9'
headers = {
    'Authorization': f'Bot {token}',
    'Content-Type': 'application/json'
}

def exists(thread_id):
    """checks if a thread with the given id exists
       TextChannel is NOT considered a thread and will show False

    Args:
        thread_id (int): id of thread

    Returns:
        bool: True if thread exists and is visible to bot
    """
    ret = requests.get(f'{base_url}/channels/{thread_id}', headers=headers)

    if ret.status_code != 200:
        return False

    content = ret.json()

    thread_type = content.get('type', 0)
    return thread_type in [10, 11, 12]  # news thread (10) and private threads (12) not tested


def name(thread_id):
    """get the name of a thread
       returns None if thread is not accessible

       calling method on channel_id will result on channel name returned

    Args:
        thread_id (int): id of thread
    
    Returns:
        str: name of the thread
    """

    ret = requests.get(f'{base_url}/channels/{thread_id}', headers=headers)

    if ret.status_code != 200:
        return None

    content = ret.json()
    return content.get('name', None)


def dearchive(thread_id):
    """try to dearchive a thread
       if the thread is not archived, returns true

    Args:
        thread_id (int): id of thread
    Returns:
        bool: True on success, aswell on no-action due to no-archive
    """
 
    status = requests.get(f'{base_url}/channels/{thread_id}', headers=headers)
    if status.status_code != 200:
        return False

    info = status.json()
    meta = info.get('thread_metadata', {})
    is_archived = meta.get('archived', True)

    if not is_archived:
        # nothing to be done, if thread is not archived
        return True

    payload = {
        'archived': False
    }

    ret = requests.patch(f'{base_url}/channels/{thread_id}', headers=headers, json=payload)
    return ret.status_code == 200


def send(thread_id, text=None, embed_json=None):
    
    payload = {}

    if text:
        payload['content'] = text

    if embed_json:
        payload['embeds'] = []
        payload['embeds'].append(embed_json)
    
    ret = requests.post(f'{base_url}/channels/{thread_id}/messages', headers=headers, json=payload)
    return ret.status_code == 200

