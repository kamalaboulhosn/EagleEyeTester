# Eagle Eye Tester
Eagle Eye Tester is a tool for testing the performance of [Eagle Eye](https://www.een.com/) live streams. The project was created when we were having latency issues with cameras when they were being accessed via [Carson](https://www.carson.live/). In an effort to try to narrow down the problem, I created this tool to determine the latency across our cameras thtat uses the [Eagle Eye API](https://apidocs.eagleeyenetworks.com/). With this information, Eagle Eye admitted that they had an issue on their end and migrated our account to a different data center, which fixed the issue entirely. I'm providing the program I used in the event it is helpful for others in the same situation.

## Requirements

* [Python](https://www.python.org/) 3.8 or later
* An [Eagle Eye](https://www.een.com/) account
* An [Eagle Eye API key](https://apidocs.eagleeyenetworks.com/#get-an-api-key)

## Installation

1. Clone this repo.
2. Enter the directory created.
3. Install the required libraries by running 
  ```sh
  pip3 install -r requirements.txt
  ```
  
## Configuration

The tool expects a JSON config file to be provided via the `-c` or `--config` command-line argument. This JSON file has the following options:

| Key                          | Type    | Required? | Description |
|------------------------------|---------|-----------|-------------|
| `email`                      | String  | Y         | The email address of the Eagle Eye account |
| `password`                   | String  | N         | The password for the Eagle Eye account. If not provided, the tool prompts for it. |
| `auth_token`                 | String  | Y         | The auth token associated with the Eagle eye account. |
| `cameras`                    | Object  | Y         | The set of cameras to test. The key is a unique name for the camera with no spaces (String). The value is the ESN (String). The ESN for a camera can be found in the [Eagle Eye Dashboard](https://www.eagleeyenetworks.com/#/dash) by looking at the information in the camera settings. |
| `delay_between_runs_seconds` | Integer | N         | The amount of time to delay between latency tests. If not specified, defaults to 60 seconds. |

A sample config file is provided in [eagle_eye.json](https://github.com/kamalaboulhosn/EagleEyeTester/blob/main/eagle_eye.json).

## Running The Tool

The tool can be run with the following command run from the directory created. This shows shows a typical execution:

```sh
python3 eagle_eye_tester.py --config eagle_eye.json latency 5
```

As executed, this command would load the config from `eagle_eye.json`, run 5 latency tests, and print out the results:

```
Load time for front_door:
	Minimum: 535ms
	Average: 622ms
	Median:  615ms
	Maximum: 685ms
Load time for back_door:
	Minimum: 551ms
	Average: 779ms
	Median:  588ms
	Maximum: 1,466ms
```

The two possible commands to run are `latency <number of runs>` and `stream <camera name>`.

The `latency` command tries to fetch the first byte from the live stream for each camera specified in the config `<number of runs>` times, with `delay_between_runs_seconds` delay between each run. The delay can be useful in the event the act of opening the stream caches any state in the Eagle Eye servers that may affect results (e.g., streams to the on-site bridge that may remain open) and you want to wait for that state to clear. Once all runs are complete, the tool prints out the minimum, average, median, and maximum load time for each stream across all runs. 

The `stream` command continually reads bytes from the stream for `<camera name>`, which is a camera that must be specified in the config file. If the stream breaks, the tool reopens it. The tool continues to read from the stream until you press `Ctrl+C`.

There are several command-line options available in the tool:

| Option                           | Required? | Description |
|----------------------------------|-----------|-------------|
| `--config <file>` or `-c <file>` | Y         | The JSON configuration file |
| `-v` or `--verbose`              | N         | Prints out more detailed information when executing |
| `-h` or `--help`                 | N         | Prints out information about running the tool. |

## License

See [LICENSE](https://github.com/kamalaboulhosn/EagleEyeTester/blob/main/LICENSE).

## Communication

Please enter an [issue](https://github.com/kamalaboulhosn/EagleEyeTester/issues) for any questions or problems you have.
