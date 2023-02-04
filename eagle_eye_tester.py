import argparse
from getpass import getpass
import json
import requests
import statistics
import time

# URLs as specifed in https://apidocs.eagleeyenetworks.com/.
AUTHENTICATE_URL = 'https://login.eagleeyenetworks.com/g/aaa/authenticate'
AUTHORIZE_URL = 'https://login.eagleeyenetworks.com/g/aaa/authorize'
PLAYBACK_URL = 'https://login.eagleeyenetworks.com/asset/play/video.flv'

# The number of bytes per read when streaming from a camera.
CHUNK_SIZE = 1024 * 10

# The threshold for which to consider a read of bytes slow.
SLOW_FETCH_THRESHOLD_MS = 5000

# The number of runs if not specified in the JSON config file.
DEFAULT_RUNS = 1

# The number of seconds between runs if not specified in the JSON config file.
DEFAULT_DELAY_BETWEEN_RUNS_SECONDS = 60


class EagleEyeTester:

  def __init__(self, config, verbose):
    self.config = config
    self.verbose = verbose

  def time_request(self, request_name, requestor):
    '''
    Time a request named `request_name` that is made via the function `requestor`
    and print out the results if `verbose` is true.
    '''
    start_time = time.time()
    response = requestor()
    end_time = time.time()
    if self.verbose:
      print('{} request took {:,}ms'.format(request_name,
                                            int((end_time - start_time) *
                                                1000)))
    return response

  def get_auth_key(self):
    '''
    Get an auth key from Eagle Eye using the user, password, and API key specified in `config`.
    '''
    auth_data = {
        'username': self.config['email'],
        'password': self.config['password']
    }
    auth_headers = {'Authentication': self.config['auth_token']}
    if self.verbose:
      print('Making authentication request')
    make_authenticaton_request = lambda: requests.post(
        AUTHENTICATE_URL, data=auth_data, headers=auth_headers)
    authenticate_response = self.time_request('Authentication',
                                              make_authenticaton_request)
    if (authenticate_response.status_code != 200):
      raise Exception('Authentication failed with code {}'.format(
          authenticate_response.status_code))

    json_response = authenticate_response.json()

    if self.verbose:
      print('Making authorize request')
    make_authorize_request = lambda: requests.post(
        AUTHORIZE_URL, data=json_response, headers=auth_headers)
    authorize_response = self.time_request('Authorize', make_authorize_request)
    if (authorize_response.status_code != 200):
      raise Exception('Authorization failed with code {}'.format(
          authorize_response.status_code))
    return authorize_response.cookies.get('auth_key')

  def make_playback_request(self, auth_key, camera_name):
    '''
    Request the live playback stream for `camera_name` using `auth_key` for the credentials.
    Returns the stream if opened successfully or throws an exception if it could not be.
    '''
    camera_id = self.config['cameras'][camera_name]
    start_time = int(time.time())
    start_timestamp = 'stream_' + str(start_time)
    playback_data = {
        'id': camera_id,
        'start_timestamp': start_timestamp,
        'end_timestamp': '+300000',
        'index': True,
        'A': auth_key
    }
    if self.verbose:
      print('Making playback request for ' + camera_name)
    make_playback_request = lambda: requests.get(
        PLAYBACK_URL, params=playback_data, stream=True)
    playback_stream = self.time_request(camera_name + ' playback',
                                        make_playback_request)
    if (playback_stream.status_code != 200):
      raise Exception('Playback for {} failed with code {}'.format(
          camera_name, playback_stream.status_code))
    return playback_stream

  def stream_repeatedly(self, camera_name):
    '''
    Receive the bytes for the live stream of `camera_name` indefinitely.
    '''
    failed_iterations = 0
    while True:
      auth_key = self.get_auth_key()
      if auth_key is None:
        print('Could not get auth key.')
        return
      playback_stream = self.make_playback_request(auth_key, camera_name)
      if playback_stream is None:
        # Exponential backoff on repeated failures.
        sleep_duration = 1 * 2**failed_iterations
        failed_iterations += 1
        print('Fetch failed, sleeping for {}s before retrying.'.format(
            sleep_duration))
        time.sleep(sleep_duration)
        continue

      failed_iterations = 0
      fetch_start = start_fetch_time = time.time()
      counter = 1
      total_size = 0
      for i in playback_stream.iter_content(CHUNK_SIZE):
        total_size += len(i)
        fetch_end = time.time()
        fetch_duration = int((fetch_end - fetch_start) * 1000)
        if (fetch_duration >= SLOW_FETCH_THRESHOLD_MS):
          print('Chunk {} took {:,}ms'.format(counter, fetch_duration))
        if (counter % 100 == 0):
          print('Read {:,} bytes in {:,}ms'.format(
              total_size, int((time.time() - start_fetch_time) * 1000)))
        counter = counter + 1
        fetch_start = time.time()
      end_fetch_time = time.time()
      print('Playback up for {:,}ms with {:,} bytes read'.format(
          int((end_fetch_time - start_fetch_time) * 1000), total_size))
      playback_stream.close()

  def test_latency(self, runs):
    '''
    Fetch the first byte of the live stream for each camera in `self.config` `runs` times.
    Pauses for `self.config.delay_between_runs_seconds` between each run. Reports the min, max,
    average, and median latency for each camera at the end.
    '''
    auth_key = self.get_auth_key()
    load_times = {}
    for camera in self.config['cameras']:
      load_times[camera] = []

    for i in range(runs):
      if i > 0:
        if self.verbose:
          print('Waiting {}s between runs.'.format(
              self.config['delay_between_runs_seconds']))
        time.sleep(self.config['delay_between_runs_seconds'])
      for camera in self.config['cameras']:
        start_time = time.time()
        playback_stream = self.make_playback_request(auth_key, camera)
        if playback_stream is not None:
          playback_stream.raw.read(1)
        end_time = time.time()
        if playback_stream is not None:
          playback_stream.close()
        load_time = end_time - start_time
        load_times[camera].append(load_time)
    for camera in load_times:
      load_times[camera].sort()
      min_load_time = int(load_times[camera][0] * 1000)
      max_load_time = int(load_times[camera][-1] * 1000)
      median_load_time = int(statistics.median(load_times[camera]) * 1000)
      total_load_time = sum(load_times[camera], 0)
      avg_load_time = int(total_load_time * 1000 / runs)
      print(
          'Load time for {}:\n\tMinimum: {:,}ms\n\tAverage: {:,}ms\n\tMedian:  {:,}ms\n\tMaximum: {:,}ms'
          .format(camera, min_load_time, avg_load_time, median_load_time,
                  max_load_time))


def get_config(file):
  '''Fetch and verify the JSON config from `file`.'''
  try:
    f = open(file, 'r')
  except FileNotFoundError:
    raise Exception('Could not find config file ' + file)

  parsed_config = {}
  try:
    parsed_config = json.load(f)
  except Exception as e:
    raise Exception('Could not parse config: ' + str(e))
  if 'email' not in parsed_config:
    raise Exception('No user found in config.')
  if 'password' not in parsed_config:
    parsed_config['password'] = getpass('Please enter Eagle Eye password:')
  if 'auth_token' not in parsed_config:
    raise Exception('No auth_token found in config.')
  if 'delay_between_runs_seconds' not in parsed_config:
    parsed_config[
        'delay_between_runs_seconds'] = DEFAULT_DELAY_BETWEEN_RUNS_SECONDS
  elif not isinstance(parsed_config['delay_between_runs_seconds'],
                      int) or parsed_config['delay_between_runs_seconds'] < 0:
    raise Exception('Invalid value for delay_between_runs_seconds ' +
                    str(parsed_config['delay_between_runs_seconds']) +
                    '. Must be number >= 0.')
  return parsed_config


def main():
  parser = argparse.ArgumentParser(
      prog='EagleEyeTester',
      description='Tests the fetching of Eagle Eye live streams.')

  parser.add_argument(
      'command',
      type=str,
      nargs='+',
      help=
      'The command to execute. Either stream <camera name> or latency <number of runs>'
  )
  parser.add_argument('-c',
                      '--config',
                      type=str,
                      required=True,
                      help='The JSON configuratiaon file')
  parser.add_argument(
      '-v',
      '--verbose',
      type=bool,
      help='Whether or not to print more details while executing')

  args = parser.parse_args()
  try:
    config = get_config(args.config)
  except Exception as e:
    print(str(e))
    exit(-1)
  verbose = args.verbose

  tester = EagleEyeTester(config, verbose)

  if (args.command[0] == 'stream'):
    if len(args.command) != 2:
      print(
          'Invalid number of arguments passed to stream command. Expect a single camera name.'
      )
      exit(-1)
    camera_name = args.command[1]
    if camera_name not in config['cameras']:
      print('No such camera ' + camera_name)
      exit(-1)
    print('Streaming ' + args.command[1] + '. Use Ctrl+C to stop.')
    try:
      tester.stream_repeatedly(args.command[1])
    except KeyboardInterrupt:
      print('Stopping streaming.')
      exit(0)
    except Exception as e:
      print('Could not stream: ' + str(e))
      exit(-1)
  elif (args.command[0] == 'latency'):
    if len(args.command) != 2:
      print(
          'Invalid argument passed to latency command. Expect a number of runs.'
      )
      exit(-1)
    runs = 0
    try:
      runs = int(args.command[1])
    except:
      print('Could not parse number of runs ' + args.command[1])
      exit(-1)
    if runs <= 0:
      print('Invalid number of runs. Must be > 0.')
      exit(-1)
    print('Testing latency')
    try:
      tester.test_latency(runs)
    except Exception as e:
      print('Could not complete latency test: ' + str(e))
      exit(-1)
  else:
    print('Invalid argument ' + args.command[0])
    exit(-1)


if __name__ == "__main__":
  main()
