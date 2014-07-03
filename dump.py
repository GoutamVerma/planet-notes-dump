from lxml import etree
import psycopg2
import psycopg2.extensions
import argparse

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)

parser = argparse.ArgumentParser(description='Exports OSM Notes from the database en masse.')
parser.add_argument('output_file', help='File to write the resulting XML to.')
parser.add_argument('--database', help='Postgres database to read from.', default='openstreetmap')
parser.add_argument('--host', help='Postgres hostname to connect to.', default='localhost')
parser.add_argument('--port', help='Postgres port to connect to.', default=5432)
parser.add_argument('--user', help='Postgres username to use when connecting to the database.', default='openstreetmap')
parser.add_argument('--password', help='Postgres password to use when connecting to the database.', default='openstreetmap')
parser.add_argument('--since', help='A datetime to retrieve notes since. Allows incremental dumps.', default='2000-01-01 00:00:00Z')

args = parser.parse_args()

outfile = file(args.output_file, 'w')
outfile.write('<?xml version="1.0" encoding="UTF-8"?>\n')
outfile.write('<osm version="0.6" generator="planet-notes-dump">\n')

conn = psycopg2.connect(host=args.host, port=args.port, user=args.user, password=args.password, database=args.database)
note_cursor = conn.cursor()
comment_cursor = conn.cursor()

note_cursor.execute("""SELECT id,latitude,longitude,created_at,status,closed_at
                       FROM notes
                       WHERE status != 'hidden' AND updated_at > %s""", [args.since])
for note in note_cursor:
    note_elem = etree.Element("note", {'lat': '%0.7f' % (note[1] / 10000000.),
                                       'lon': '%0.7f' % (note[2] / 10000000.)})

    id_elem = etree.SubElement(note_elem, "id")
    id_elem.text = str(note[0])

    created_elem = etree.SubElement(note_elem, "date_created")
    created_elem.text = note[3].strftime('%Y-%m-%d %H:%M:%S UTC')

    if note[4] == 'closed':
        closed_elem = etree.SubElement(note_elem, "date_closed")
        closed_elem.text = note[5].strftime('%Y-%m-%d %H:%M:%S UTC')

    comments_elem = etree.SubElement(note_elem, "comments")

    comment_cursor.execute("""SELECT created_at,author_id,users.display_name,body,event
                              FROM note_comments
                              FULL OUTER JOIN users ON (note_comments.author_id=users.id)
                              WHERE note_id = %s ORDER BY created_at""", [note[0]])
    for comment in comment_cursor:
        comment_elem = etree.SubElement(comments_elem, "comment")

        comment_date_elem = etree.SubElement(comment_elem, "date")
        comment_date_elem.text = comment[0].strftime('%Y-%m-%d %H:%M:%S UTC')

        if comment[1]:
            comment_uid_elem = etree.SubElement(comment_elem, "uid")
            comment_uid_elem.text = str(comment[1])

            comment_user_elem = etree.SubElement(comment_elem, "user")
            comment_user_elem.text = comment[2]

        comment_action_elem = etree.SubElement(comment_elem, "action")
        comment_action_elem.text = comment[4]

        if comment[3] is not None:
            comment_text_elem = etree.SubElement(comment_elem, "text")
            comment_text_elem.text = comment[3]

    outfile.write(etree.tostring(note_elem, encoding='utf8', pretty_print=True))

    if note_cursor.rownumber % 100 == 0:
        print "Wrote out note %6d. (%6d of %6d)" % (note[0], note_cursor.rownumber, note_cursor.rowcount)

print "Wrote out note %6d. (%6d of %6d)" % (note[0], note_cursor.rownumber, note_cursor.rowcount)

conn.close()

outfile.write('</osm>\n')
outfile.close()
