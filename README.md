# Show docker image family tree

## Usage and options
```
usage: docker_tree.py [-h] [-r | -l | -I] [-N]
                      [<image id or tag> [<image id or tag> ...]]

Shows docker image family tree.

positional arguments:
  <image id or tag>    Show the family tree of a particular image

optional arguments:
  -h, --help           show this help message and exit
  -r, --roots          Show only "root" images
  -l, --leafs          Show only "leaf" images
  -I, --always-indent  Always show indented tree
  -N, --no-trunc       Do NOT truncate image id's to 12 chars
```

## Deffault output
```
$ docker_tree.py
alpine:3.17: 2022.11.22 22:19:29, 6.7M
└───tesseract-alpine:2022.12.26.001: 2022.12.26 11:48:35, +723M
    └───9c90a8e98171: +21:54
        └───7ed3681fa476: +0.3K
            └───03dc693d9c60
                └───tesseract-alpine:latest,tesseract-alpine:2022.12.26.002
ubuntu:22.04: 2022.10.04 23:35:20, 74M
└───7c7a7c3c7dc7: 2022.12.18 07:38:36, +863M
    └───07edb627b42b: +1s, +0.3K
        └───095a0b6740a1
            └───583ffde90533
                └───78d744e6bee1
                    └───83163f244422: +2s
                        └───tesseract:latest,tesseract:2022.12.18.001: +1s
```

## Without truncation
```
$ docker_tree.py -N
alpine:3.17: 2022.11.22 22:19:29, 6.7M
└───tesseract-alpine:2022.12.26.001: 2022.12.26 11:48:35, +723M
    └───9c90a8e98171899ea83a1d07d13482fd48c35e6312a8e1f168cc2294a11ca557: +21:54
        └───7ed3681fa4764d8e396a7973c033bc277eb1d9653d65fee600acc84d776d33cf: +0.3K
            └───03dc693d9c60e6ddda0559255f56b847752dc61c077a48bb2f6782f9b0d3908e
                └───tesseract-alpine:latest,tesseract-alpine:2022.12.26.002
ubuntu:22.04: 2022.10.04 23:35:20, 74M
└──7c7a7c3c7dc74f63157ee4600b9ee0c899c1740704e2f015865ef9f8f4bf2b5a: 2022.12.18 07:38:36, +863M
   └───07edb627b42b58003e44076990e7ff075bd3cc9eba8b54f8e7e8c62146305103: +1s, +0.3K
       └───095a0b6740a15cf5e61940b199b7c92afdb45d9bbf05b70ca8df864f980695da
           └───583ffde90533050f7102c0a8339db489d09f07e5545dc37cc5ad656d55c997b2
               └───78d744e6bee14559cccb76c7a1d5066ed6eac32c235fea4c630875f33538ca9b
                   └───83163f244422c49ac16bfc2e531f225d1165cd5ae5637b7d0e3bfbeceb936345: +2s
                       └───tesseract:latest,tesseract:2022.12.18.001: +1s
```

## Roots: images that were not built localy
```
$ docker_tree.py -r
alpine:3.17: 2022.11.22 22:19:29, 6.7M
ubuntu:22.04: 2022.10.04 23:35:20, 74M
```

## Leafs: end-result images
```
$ docker_tree.py -l
tesseract-alpine:latest,tesseract-alpine:2022.12.26.002: 2022.12.26 12:10:31, 730M
tesseract:latest,tesseract:2022.12.18.001: 2022.12.18 07:38:43, 937M
```

## Tree for one image
```
$ docker_tree.py tesseract-alpine:2022.12.26.001
┌─alpine:3.17: 2022.11.22 22:19:29, 6.7M
└─• tesseract-alpine:2022.12.26.001: 2022.12.26 11:48:35, +723M
    └───9c90a8e98171: +21:54
        └───7ed3681fa476: +0.3K
            └───03dc693d9c60
                └───tesseract-alpine:latest,tesseract-alpine:2022.12.26.002
```

## Leaf(s) for one image
```
$ docker_tree.py -l tesseract-alpine:2022.12.26.001
tesseract-alpine:latest,tesseract-alpine:2022.12.26.002: 2022.12.26 12:10:31, 730M
```

## Root of one image
```
$ docker_tree.py -r tesseract-alpine:2022.12.26.001
alpine:3.17: 2022.11.22 22:19:29, 6.7M
```

## Tree for several images
```
$ docker_tree.py tesseract tesseract-alpine
alpine:3.17: 2022.11.22 22:19:29, 6.7M
└───tesseract-alpine:2022.12.26.001: 2022.12.26 11:48:35, +723M
    └───9c90a8e98171: +21:54
        └───7ed3681fa476: +0.3K
            └───03dc693d9c60
                └─• tesseract-alpine:latest,tesseract-alpine:2022.12.26.002
ubuntu:22.04: 2022.10.04 23:35:20, 74M
└───7c7a7c3c7dc7: 2022.12.18 07:38:36, +863M
    └───07edb627b42b: +1s, +0.3K
        └───095a0b6740a1
            └───583ffde90533
                └───78d744e6bee1
                    └───83163f244422: +2s
                        └─• tesseract:latest,tesseract:2022.12.18.001: +1s
```

## TODO
```
  -u, --untagged       Show only branches ending with untagged "leaf" images
  -p, --page           Pipe output to \$PAGER program
  -P, --page-thru <command>
                       Pipe output through given command, ex. "less -S"
```