

class test_hook:
    """ hook used for testing --processor option to main """
    def add(control, source, parts):
        control.add("""
            assert(@all(test_hook_was_here)).
            assert(@models(1)).
            """)
        control.add(source)


