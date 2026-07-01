#!/bin/bash
# Fetch camera stats for all Fusus communities
./scrape-fusus.py

# Download Seattle specific web pages for page diff tracking
./download.sh 'https://communityconnectseattle.org/'
./download.sh 'https://communityconnectseattle.org/camera-registration/'
./download.sh 'https://communityconnectseattle.org/camera-integration/'
./download.sh 'https://communityconnectseattle.org/join/'
./download.sh 'https://communityconnectseattle.org/privacy-policy/'

