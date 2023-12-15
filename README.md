# Dela's Bountycatch.py remix 🎀

This repository contains *my remix* of Jason Haddix's  [`bountycatch.py`](https://gist.github.com/jhaddix/91035a01168902e8130a8e1bb383ae1e) script. The original script was simple and easier to manage, and I just added my own twist so it could do other commands I need 🧸.
(Note: courtesy of this script goes to Jason Haddix. I just added some features that I wanted there ❤️)

## Overview

`BountyCatch` is a simple  Python script that helps in managing subdomains for your bug bounty projects. It reads subdomains from a text file, ensuring that no duplicates are stored. It uses Redis DB to save the subdomains. 

## Features (as for now)

- Save subdomains into a database from text files.
- Eliminate duplicate subdomain entries.
- Count the number of unique subdomains.
- Delete a specific subdomain entry.

## Prerequisites

Before you get started, you'll need to have Redis installed on your system. 

## Installing Redis on Linux

Follow these steps to install Redis on your Linux system. The below command will install Redis on your system and start it as a service :) 

```bash
sudo apt update
sudo apt install redis-server
```

## Usage
Below are the commands available for Bountycatch:

### Adding Subdomains
To add subdomains for a project:

```bash
python3 bountycatch.py --project xyz.com --o add --file xyz_subdomains.txt
```
### Printing Current Project Data
To display the current project's subdomains:

```bash
python3 bountycatch.py --project xyz.com -o print
```

### Counting Subdomains
To count the number of subdomains for the current project:

```bash
python3 bountycatch.py --project xyz.com -o count
```

### Deleting a Subdomain
To delete a specific subdomain from the project:

```bash
python3 bountycatch.py --project xyz.com -o delete 
```


