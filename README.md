# Microphone: tools for blocking ads in Megaphone-hosted podcasts

I was listening to a podcast hosted through Megaphone, and I noticed that it had dynamically-inserted ads show up a few years into the show's run. Right now, for example, it really wants to sell me the Kpop Demon Hunters meal at McDonalds.

I will not be purchasing the Kpop Demon Hunters meal at McDonalds, so I decided to make a tool to drop the dynamic ads from the podcast.

# Usage as a Docker Container

Run the Microphone ad-filtering proxy server server (`server.py`) as a Docker container:
```
docker run -ti --rm -p 127.0.0.1:8080:8080 quay.io/interfect/microphone:latest
```

Then go to [http://127.0.0.1:8080](http://127.0.0.1:8080) to access the web UI.

Enter an `https://feed.megaphone.fm` URL in the `Get Feed` form, and add the resulting URL to your podcatcher as a feed. Each episode will be filtered to remove ads before streaming a clean version to your podcatcher. You can also use the `Get Episode` form to stream a single episode.

(If your podcatcher is on a different device, like a phone, you will need to replace `127.0.0.1` here with an IP address that your podcast-listening device can reach.)

For an Internet-facing deployment, if you want to run a private instance for just yourself or a few authorized users, you can set a secret "token" to authenticate requests. This can be set through the `MICROPHONE_TOKEN` environment variable, and needs to be only English letters, numbers, and dashes.
```
docker run -ti --rm -e MICROPHONE_TOKEN=8a12aa64-37c0-11f1-96aa-077586b680f4 -p 127.0.0.1:8080:8080 quay.io/interfect/microphone:latest
```
This makes the forms on the homepage (and the API) require the token. You can include the token in the homepage URL to pre-fill it, like [http://127.0.0.1:8080?token=8a12aa64-37c0-11f1-96aa-077586b680f4](http://127.0.0.1:8080?token=8a12aa64-37c0-11f1-96aa-077586b680f4).

## Permanent Deployment with Docker Compose

To integrate with an existing Docker-Compose-managed set of services, add something like this to your `docker_compose.yml`:
```
  microphone:
    image: quay.io/interfect/microphone:latest
    environment:
      # This is the default port but we keep it here for reference
      - "MICROPHONE_PORT=8080"
      - "MICROPHONE_TOKEN=<insert UUID here>"
    labels:
      # If you're using Traefik and Let's Encrypt, these labels will expose the service on a subdomain.
      - "traefik.enabled=true"
      - "traefik.http.routers.microphone.rule=Host(`yourhost.yourdomain.tld`)"
      - "traefik.http.routers.microphone.certResolver=leresolver"
      - "traefik.http.services.microphone-service.loadbalancer.server.port=8080"
    restart: always
```

# Usage as a Command Line Tool

Right now, there's nothing to process an RSS feed or host an episode-processing proxy; you can only fetch a single episode at a time from its `https://traffic.megaphone.fm/XXXXXXX.mp3?XXXXXXX` URL.

1. Clone the repo:
```
git clone https://github.com/interfect/microphone
```
2. Enter the directory
```
cd microphone
```
3. Run `fetch.py` on your URL, and redirect output to an MP3 file:
```
python3 fetch.py 'https://traffic.megaphone.fm/XXXXXXX.mp3?XXXXXXX' >clean-episode.mp3
```
4. Listen to the episode in blissful ignorance of the content of dynamic ads!
5. To run the server without Docker:
```
python3 server.py
```
Also make sure to check out `python3 server.py --help`.

# How It Works

Other podcast ad-removal tools like [MinusPod](https://github.com/ttlequals0/MinusPod) work by using AI transcription and ad-guessing, so they work even on fixed sponsor segments that are part of the "real" episode, but they require expensive language models to function.

Microphone only works on dynamically-inserted ads that change depending on the listener, and (right now) only on Megaphone podcasts, but it uses a much simpler method.

See, MP3 files are composed of "frames" that each represent a snippet of audio. Megaphone is lazy when it inserts ads into a podcast episode: it re-uses all the frames from the original ad-free source episode, and pastes the ad frames into the file alongside them.

Microphone requests several copies of a podcast episode from Megaphone, each of which is a distinct download that gets assigned its own set of ads. Microphone then compares the files, and throws away any MP3 frames that don't appear in *all* versions of the episode, with some additional logic to remove frames that do appear in all episodes but move around the file like they're slotting into ad slots. As long as there isn't an ad that got added to all versions of the episode at the same place, this results in throwing out all the ads and keeping just a clean copy of the ad-free episode. No fancy AI models needed.

To parse MP3 frames, Microphone uses a slightly modified version of part of https://github.com/kirkeby/python-mp3, by Sune Kirkeby.

