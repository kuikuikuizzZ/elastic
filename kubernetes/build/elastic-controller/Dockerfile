#
# Copyright 2018 The Caicloud Authors.
#

FROM cargo.caicloud.xyz/library/debian:stretch

LABEL maintainer="wuwenhui <wuwenhui.wuwh@bytedance.com>"

ADD bin/elastic-controller /elastic-controller

ENTRYPOINT ["/elastic-controller"]
