.PHONY: configure build test validate doctor clean

PYTHON ?= python3
CMAKE ?= cmake
BUILD_DIR ?= build
BUILD_TYPE ?= RelWithDebInfo
CMAKE_ARGS ?= -G Ninja -DCMAKE_EXPORT_COMPILE_COMMANDS=1 -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_C_COMPILER=clang

configure:
	$(CMAKE) -S . -B $(BUILD_DIR) -DCMAKE_BUILD_TYPE=$(BUILD_TYPE) $(CMAKE_ARGS)

build: configure
	$(CMAKE) --build $(BUILD_DIR) --parallel

test:
	PYTHONPATH=python $(PYTHON) -m unittest discover -s tests -v

validate:
	PYTHONPATH=python $(PYTHON) -m orchestrator validate --scenarios scenarios

doctor:
	PYTHONPATH=python $(PYTHON) -m orchestrator doctor --config environment/toolchain.json

clean:
	$(PYTHON) -c "import shutil; shutil.rmtree('build', ignore_errors=True)"
