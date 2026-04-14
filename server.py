#!/usr/bin/env python3

# Run a proxy translating Megaphone feeds and preprocessing episodes to remove ads.

import argparse
import hmac
import os
import re
import shutil
import socket
import sys
import traceback
import urllib.parse
import urllib.request

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from fetch import stream_clean

# Authentication tokens must match this pattern.
# The pattern needs to allow only characters that do not need HTML or URL escaping.
TOKEN_REGEX="[a-zA-Z0-9-]+"

# We're pretty sure actual remote URLs won't be longer than this. It should be
# short enough that not much can be gotten up to within it.
MAX_REMOTE_URL_LENGTH = 128

class MicrophoneHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    Class implementing feed proxying and episode preprocessing.
    
    Gets instantiated for each request.
    
    See
    <https://docs.python.org/3/library/http.server.html#http.server.BaseHTTPRequestHandler>
    for how Python's rarely-used built-in web service system works.
    
    Presents a server with an index page, a method for retrieving a feed, and a
    method for retrieving a filtered episode.
    
    All the actual podcast-related methods have optional token authentication,
    where the provided token field needs to match the class's token if set.
    """
    
    # Class-level token for authentication, or None.
    # Can only contain alphanumeric characters and "-"
    expected_token = None
    
    # Class-level base URL for the API to put in references back to it in the feed.
    base_url = None
    
    
    def do_GET(self):
        """
        Called when a GET request comes in.
        
        Responsible for checking instance fields like path and calling
        something like send_response(), end_headers(), and then writing content
        to wfile.
        """
        
        try:
            parsed_url = urllib.parse.urlsplit(self.path)
            try:
                # Parse as much query string as we allow
                query_dict = urllib.parse.parse_qs(parsed_url.query, max_num_fields=2, strict_parsing=True)
            except ValueError:
                self.send_error(400, "Query string not acceptable")
                return
            # Figure out what API endpoint they want
            if parsed_url.path == "/feed":
                # This is a request for a feed
                self.handle_proxy_feed(query_dict)
            elif parsed_url.path == "/episode":
                # This is a request for an episode
                self.handle_proxy_episode(query_dict)
            elif parsed_url.path in ("/", "/index.html"):
                # If they just show up, give them a homepage
                self.handle_homepage(query_dict)
            else:
                self.send_error(404, "Page Not Found")
        except Exception as e:
            self.log_error("Internal error: %s", traceback.format_exc())
            self.send_error(500, "Internal Server Error")
        
    def _get_token(self, query_dict):
        """
        Get the token, if it matches the required format, or None if none was
        provided or it does not match the format.
        """
        
        if "token" not in query_dict:
            return None
        if len(query_dict["token"]) != 1:
            return None
        
        provided_token = query_dict["token"][0]
        
        if not re.fullmatch(TOKEN_REGEX, provided_token):
           return None
       
        return provided_token
    
    def _check_token(self, query_dict):
        """
        Check for the right token being there if authentication with tokens is
        required.
        
        If authentication is required and not provided, sends a permission
        error and returns False. Otherwise returns True.
        
        TODO: Could become a decorator.
        """
        if self.expected_token is not None:
            provided_token = self._get_token(query_dict)
            # Do a constant-time token comparison to avoid timing attacks on the token
            if provided_token is None or not hmac.compare_digest(provided_token, self.expected_token):
                self.send_error(401, "Incorrect token in query")
                return False
            
        return True
    
    def _validate_query_url(self, prefix, query_dict):
        """
        Make sure that a URL was provided, that it has the given prefix, and
        that it isn't too long.
        
        If the URL is not acceptable, sends an error and returns None.
        
        Otherwise, returns the URL.
        """
        
        if "url" not in query_dict or len(query_dict["url"]) != 1:
            self.send_error(400, "Exactly one URL is required")
            return None
        
        remote_url = query_dict.get("url")[0]
        
        if not remote_url.startswith(prefix):
            self.send_error(400, f"URL does not start with correct prefix {prefix}")
            return None
        
        if len(remote_url) > MAX_REMOTE_URL_LENGTH:
            self.send_error(400, "URL is too long")
            return None
        
        return remote_url
            
        
    def handle_proxy_feed(self, query_dict):
        self.log_message("Proxy a feed")
        if not self._check_token(query_dict):
            return
        
        remote_url = self._validate_query_url("https://feeds.megaphone.fm/", query_dict)
        if remote_url is None:
            return
        
        # Links we generate will need to include the token if available.
        provided_token = self._get_token(query_dict)
        
        # We're going to fix up all the episode URLs in the feed with a
        # callback that encodes them into URLs to us. See
        # <https://stackoverflow.com/a/2095012>
        def url_callback(match):
            """
            Return replacement text for a regex match.
            """
            base = self.base_url if self.base_url is not None else ""
            parts = [f"{base}episode?url={urllib.parse.quote(match.group(0), safe='')}"]
            if provided_token is not None:
                parts.append(f"token={provided_token}")
            # We need to use XML entities for the ampersands we add.
            return "&amp;".join(parts)
            
        
        feed_lines = []
        with urllib.request.urlopen(remote_url) as feed_in:
            if feed_in.status != 200:
                # We're not getting the feed, error
                self.send_error(502, "Could not retrieve feed")
                return
            
            # Otherwise start the response
            self.send_response(200, "OK")
            self.end_headers()
                
            for line in feed_in:
                # Grab each line
                decoded_line = line.decode("utf-8")
                # Invoke Zalgo
                # TODO: We know there URLs do not in fact contain XML entities.
                modified_line = re.sub(r'https://traffic\.megaphone\.fm/[^"\' ]*', url_callback, decoded_line)
                # Send the modified lines as we get them.
                self.wfile.write(modified_line.encode("utf-8"))
        
    def handle_proxy_episode(self, query_dict):
        self.log_message("Proxy an episode")
        if not self._check_token(query_dict):
            return
        
        remote_url = self._validate_query_url("https://traffic.megaphone.fm/", query_dict)
        if remote_url is None:
            return
        
        # Just assume we'll get the episode.
        self.send_response(200, "OK")
        self.end_headers()
        stream_clean(remote_url, self.wfile, log=lambda message: self.log_message("%s", message))
            
        
    def handle_homepage(self, query_dict):
        self.log_message("Send homepage")
        
        def make_token_field(form_name):
            """
            Produce HTML for a labeled form field for a "token" parameter to go in the
            form with the given name, if authentication is required.
            
            The field will be pre-filled with the provided token if a token is
            provided in the index URL.
            """
            token_field = ""
            if self.expected_token is None:
                return ""
            
            provided_token = self._get_token(query_dict) or ""
            
            return f"""
            <label for="{form_name}_token">Authentication Token:</label>
            <input id="{form_name}_token" name="token" type="password" autocomplete="current-password" value="{provided_token}" required/>
            """
        
        self.send_response(200, "OK")
        self.end_headers()
        self.wfile.write(f"""
        <!DOCTYPE html>
        <html>
            <head>
                <title>Microphone Podcast Proxy</title>
            </head>
            <body>
                <h1>Microphone Podcast Proxy</h1>
                <hr/>
                <p>Microphone is a tool for listening to podcasts hosted via Megaphone, without dynamically-inserted ads. You have reached Microphone's built-in ad-filtering podcast proxy, designed to allow you to add an ad-free version of a podcast to your podcatcher of choice.</p>
                <p>If you aren't running this Microphone proxy server, you might want to ask permission to use it.</p>
                <p>Note that Microphone <b>cannot</b> filter out ads that are actually part of podcast episodes; it can only filter out dynamically-inserted Megaphone ads.</p>
                <section>
                    <h2>Get Feed</h2>
                    <p>Enter the URL of a Megaphone podcast RSS feed to get a feed URL for your podcatcher.</p>
                    <form method="GET" action="/feed">
                        <label for="feed_url">Feed URL:</label>
                        <input id="feed_url" type="url" name="url" placeholder="https://feeds.megaphone.fm/..." pattern="https://feeds.megaphone.fm/.*" required />
                        {make_token_field("feed")}
                        <input type="submit"/>
                    </form>
                </section>
                <section>
                    <h2>Get Episode</h2>
                    <p>Enter the URL of a Megaphone podcast episode to retrieve the episode and not the ads.</p>
                    <form method="GET" action="/episode">
                        <label for="episode_url">Episode URL:</label>
                        <input id="episode_url" type="url" name="url" placeholder="https://traffic.megaphone.fm/..." pattern="https://traffic.megaphone.fm/.*" required />
                        {make_token_field("episode")}
                        <input type="submit"/>
                    </form>
                </section>
                <section>
                    <h2>Get Source</h2>
                    <p>View the <a href="https://github.com/interfect/microphone/">source code</a> and find out how to run your own Microphone proxy server.</p>
                </section>
            </body>
        </html>
        """.encode("utf-8"))
        pass
    

if __name__ == "__main__":
    DEFAULT_ADDRESS = "::"
    DEFAULT_PORT = 8080
    
    parser = argparse.ArgumentParser(
        sys.argv[0],
        description="Ad-removing podcast proxy server",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Token (nonempty and containing only A-Z, a-z, 0-9, and -) to require in URLs for access control. Read from MICROPHONE_TOKEN in the environment if not provided."
    )
    parser.add_argument(
        "--address",
        default=None,
        help=f"Listen address for the server. Read from MICROPHONE_ADDRESS in the environment if not provided. Default: {DEFAULT_ADDRESS}"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Port for the server to listen on. Read from MICROPHONE_PORT in the environment if not provided. Default: {DEFAULT_PORT}"
    )
    parser.add_argument(
        "--base_url",
        default=None,
        help=f"Hostname and path to include in URLs in the feed, to point back to the server. Read from MICROPHONE_BASE_URL in the environment if not provided. Default: none"
    )
    options = parser.parse_args(sys.argv[1:])
    
    if options.token is None:
        options.token = os.environ.get("MICROPHONE_TOKEN") or None
        
    if options.address is None:
        options.address = os.environ.get("MICROPHONE_ADDRESS", DEFAULT_ADDRESS)
    
    if options.port is None:
        try:
            options.port = int(os.environ.get("MICROPHONE_PORT", DEFAULT_PORT))
        except ValueError:
            sys.stderr.write("Error: MICROPHONE_PORT is not an integer\n")
            sys.exit(1)
            
    if options.base_url is None:
        options.base_url = os.environ.get("MICROPHONE_BASE_URL") or None
    if options.base_url is not None and not options.base_url.endswith("/"):
        # Add a trailing slash so we can concatenate with relative paths
        options.base_url += "/"
        
    MicrophoneHTTPRequestHandler.base_url = options.base_url
    
    if ':' in options.address:
        # TODO: Python 3.9+ should support IPv6 here automatically, but doesn't.
        # The workaround is to make sure the server class has the right address family.
        ThreadingHTTPServer.address_family = socket.AF_INET6
        link_address = f"[{options.address}]"
    else:
        link_address = options.address
        
    if options.token is not None:
        if not re.fullmatch(TOKEN_REGEX, options.token):
            # Make sure the token is one we can actually get
            sys.stderr.write("Error: --token must contain only A-Z, a-z, 0-9, and -, and must be nonempty if set\n")
            sys.exit(1)
        MicrophoneHTTPRequestHandler.expected_token = options.token
    
    # Set up the server
    server = ThreadingHTTPServer((options.address, options.port), MicrophoneHTTPRequestHandler)
    
    # Announce the link
    sys.stderr.write(f"Starting server on http://{link_address}:{options.port}/")
    if options.token is not None:
        # Include the token in the log so our expected single user can click the link and have it filled.
        sys.stderr.write(f"?token={options.token}")
    sys.stderr.write("\n")
    
    # Run the server
    server.serve_forever()
    
