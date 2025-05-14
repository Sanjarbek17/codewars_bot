from tinydb import TinyDB, Query

# Initialize TinyDB
db = TinyDB("database/db.json")
users_table = db.table("users")
groups_table = db.table("groups")


def get_user(telegram_id):
    """Get user by telegram ID."""
    User = Query()
    return users_table.get(User.telegram_id == telegram_id)


def update_user(telegram_id, data):
    """Update user data."""
    User = Query()
    users_table.upsert(data, User.telegram_id == telegram_id)


def get_user_groups(telegram_id):
    """Get groups user belongs to."""
    Group = Query()
    return groups_table.search(Group.members.any([telegram_id]))


def create_group(name, creator_id):
    """Create a new group."""
    Group = Query()
    if not groups_table.search(Group.name == name):
        groups_table.insert(
            {"name": name, "creator_id": creator_id, "members": [creator_id]}
        )
        return True
    return False


def update_group(group_name, data):
    """Update group data."""
    Group = Query()
    groups_table.update(data, Group.name == group_name)


def add_user_to_group(group_name, user_id):
    """Add user to group."""
    Group = Query()
    group = groups_table.get(Group.name == group_name)
    if group and user_id not in group["members"]:
        group["members"].append(user_id)
        groups_table.update(group, Group.name == group_name)
        return True
    return False


def get_group(group_name):
    """Get group by name."""
    Group = Query()
    return groups_table.get(Group.name == group_name)
