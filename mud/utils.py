from itertools import groupby


def condition(usage, max_usage, conditions):
    """
    >>> conditions = ['slightly used', 'used', 'well-used', 'worn out', 'falling apart']
    >>> condition(1, 3, conditions)
    'used'
    >>> condition(2, 3, conditions)
    'falling apart'
    >>> condition(1, 5, conditions)
    'slightly used'
    >>> condition(2, 5, conditions)
    'used'
    >>> condition(3, 5, conditions)
    'well-used'
    >>> condition(4, 5, conditions)
    'falling apart'
    """
    index = int(round(usage / (max_usage - 1) * (len(conditions) + 1))) - 2
    return conditions[index] if index >= 0 else str()


def credits(x):
    if not x:
        return "no credits"
    if x > 1:
        return "{x:d} credits"
    return "1 credit"


def list_sentence(names, glue=None):
    """
    >>> list_sentence(['apples'])
    'apples'

    >>> list_sentence(['apples', 'oranges'])
    'apples and oranges'

    >>> list_sentence(['apples', 'oranges', 'democratic republic'])
    'apples, oranges and democratic republic'
    """

    glue = glue or 'and'
    names = list(names)
    if len(names) == 1:
        return names.pop(0)
    return "%s %s %s" % (', '.join(n for n in names[:-1]), glue, names[-1])


def pretty_list(item_or_items):
    """
    >>> pretty_list([])
    'nothing'

    >>> Item = type('Item', (object,), dict(name='an item'))
    >>> pretty_list(Item())
    'an item'

    >>> pretty_list([Item()])
    'an item'

    >>> pretty_list([Item(), Item()])
    'an item and an item'

    >>> PluralItem = type('Item', (object,), dict(name='an item', plural='%d items'))
    >>> pretty_list([PluralItem(), PluralItem()])
    '2 items'

    >>> the_item = PluralItem()
    >>> the_item.name = 'the item'
    >>> pretty_list([Item(), Item(), PluralItem(), PluralItem(), the_item])
    'an item, an item, 2 items and the item'
    """

    if hasattr(item_or_items, 'name'):
        return item_or_items.name

    items = list(item_or_items)

    if len(items) == 0:
        return 'nothing'

    if len(items) == 1:
        return items.pop(0).name

    return list_sentence(label for label, speciment in group_by_class(items))


def get_name(i):
    if hasattr(i, 'name_with_condition'):
        return i.name_with_condition
    else:
        return i.name


def group_by_class(items):
    items = sorted(items, key=lambda i: type(i).__name__)
    grouped = groupby(items, lambda i: (type(i), get_name(i)))
    for (cls, name), group in grouped:
        group = list(group)
        count = len(group)

        specimen = group[0]
        if count > 1 and hasattr(specimen, 'plural'):
            if callable(specimen.plural):
                yield specimen.plural(count), specimen
            else:
                yield specimen.plural % count, specimen
        else:
            for item in group:
                yield name, item


class FilterSet(set):
    def filter(self, cls):
        return (i for i in self if isinstance(i, cls))
