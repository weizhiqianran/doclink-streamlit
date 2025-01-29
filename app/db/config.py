from configparser import ConfigParser


class GenerateConfig:
    def __init__(self) -> None:
        pass

    def config(filename="app/db/database.ini", section="postgresql"):
        parser = ConfigParser()
        parser.read(filename)
        db_config = {}
        if parser.has_section(section):
            params = parser.items(section)
            for param in params:
                db_config[param[0]] = param[1]
        else:
            raise Exception(f"Section {section} is not found in {filename} file.")
        return db_config
