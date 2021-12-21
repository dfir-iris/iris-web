PYTHONCMD=python3 
REPORT=report.txt
TESTFOLDER=tests

test : test_all log
test_pipelines: pipeline_target log

test_all:
	@$(PYTHONCMD) -m unittest $(TESTFOLDER)/main.py 2> $(REPORT) 

pipeline_target:
	@$(PYTHONCMD) -m unittest $(TESTFOLDER)/test_kbh_pipelines.py 2> $(REPORT) 

log:
	@echo "Test report stored in $(REPORT)"