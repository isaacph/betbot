#!/bin/bash
set -e

# script to automatically zip
rm ../../../../function.zip || true
cd env/lib/python3.10/site-packages
zip -r ../../../../function.zip .
cd ../../../..
zip function.zip lambda_function.py public_key.py
