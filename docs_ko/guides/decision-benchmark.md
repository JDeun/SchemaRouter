# Decision benchmark

bounded decision backend의 품질은 integration 가능 여부와 별도로 측정합니다. benchmark는 versioned multilingual/adversarial corpus와 calibration/holdout split을 사용하고 exact route, unsupported rejection, false route, calibration/abstention, latency/error를 machine-readable artifact로 기록합니다.

threshold는 development/calibration data에서만 조정하고 holdout 결과를 본 뒤 다시 맞추지 않습니다. provider/model/hardware/revision을 고정하고 deterministic baseline과 같은 workload에서 비교합니다. model이 finite option contract를 지켰는지와 execution-authority violation이 없었는지도 별도 확인합니다.

live provider outage나 infrastructure failure는 scientific failure와 분리합니다. promotion은 preregistered gate를 통과한 fresh evidence가 있을 때만 이루어집니다.
