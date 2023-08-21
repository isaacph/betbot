#!/bin/bash
set -e

./zip.sh
aws s3 cp ./function.zip s3://betbot-source
aws lambda update-function-code --function-name discord_bet_bot --s3-bucket betbot-source --s3-key function.zip
