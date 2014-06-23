from uber.common import *

@all_renderable(PEOPLE)
class Root:
    def index(self, session, message='', order='name', show='all'):
        which = {
            'all':    [],
            'tables': [Group.tables > 0],
            'groups': [Group.tables == 0]
        }[show]
        # TODO: think about using a SQLAlchemy column property for .badges and then just use .order()
        groups = sorted(session.query(Group).filter(*which).options(joinedload('attendees')).all(),
                        reverse=order.startswith('-'),
                        key=lambda g: [getattr(g, order.lstrip('-')), g.tables])
        return {
            'show':              show,
            'groups':            groups,
            'message':           message,
            'order':             Order(order),
            'total_groups':      len(groups),
            'total_badges':      sum(g.badges for g in groups),
            'tabled_badges':     sum(g.badges for g in groups if g.tables),
            'untabled_badges':   sum(g.badges for g in groups if not g.tables),
            'tabled_groups':     len([g for g in groups if g.tables]),
            'untabled_groups':   len([g for g in groups if not g.tables]),
            'tables':            sum(g.tables for g in groups),
            'unapproved_tables': sum(g.tables for g in groups if g.status == UNAPPROVED),
            'waitlisted_tables': sum(g.tables for g in groups if g.status == WAITLISTED),
            'approved_tables':   sum(g.tables for g in groups if g.status == APPROVED)
        }

    def form(self, session, message='', **params):
        group = session.group(params, bools=['auto_recalc','can_add'])
        if 'name' in params:
            message = check(group)
            if not message:
                session.add(group)
                message = group.assign_badges(params['badges'])
                if not message:
                    if 'redirect' in params:
                        raise HTTPRedirect('../preregistration/group_members?id={}', group.secret_id)
                    else:
                        raise HTTPRedirect('form?id={}&message={}', group.id, 'Group info uploaded')
        return {
            'message': message,
            'group':   group
        }

    @ajax
    def unapprove(self, session, id, action, email):
        assert action in ['waitlisted', 'declined']
        group = session.group(id)
        subject = 'Your MAGFest Dealer registration has been ' + action
        send_email(MARKETPLACE_EMAIL, group.email, subject, email, model = group)
        if action == 'waitlisted':
            group.status = WAITLISTED
        else:
            for attendee in group.attendees:
                session.delete(attendee)
            session.delete(group)
        session.commit()
        return {'success': True}

    @csrf_protected
    def delete(self, session, id):
        group = session.group(id)
        if group.badges - group.unregistered_badges:
            raise HTTPRedirect('form?id={}&message={}', id, "You can't delete a group without first unassigning its badges.")
        else:
            for attendee in group.attendees:
                session.delete(attendee)
            session.delete(group)
            raise HTTPRedirect('index?message={}', 'Group deleted')
