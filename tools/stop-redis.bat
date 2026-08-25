@echo off
"%~dp0redis\redis-cli.exe" -p 6379 shutdown nosave
