from itertools import groupby


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


def group_by_class(items):
    items = sorted(items, key=lambda i: i.name)
    grouped = groupby(items, lambda i: (type(i), i.name))
    for (cls, name), group in grouped:
        group = list(group)
        count = len(group)

        if count > 1 and hasattr(cls, 'plural'):
            specimen = group.pop(0)
            if callable(cls.plural):
                yield cls.plural(count), specimen
            else:
                yield cls.plural % count, specimen
        else:
            for item in group:
                yield item.name, item


class FilterSet(set):
    def filter(self, cls):
        return (i for i in self if isinstance(i, cls))
