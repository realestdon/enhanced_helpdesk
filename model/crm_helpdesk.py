# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2014 Apulia (<info@apuliasoftware.it>)
#    All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


from openerp import models, fields, api, SUPERUSER_ID


class CrmHelpdesk(models.Model):

    _inherit = "crm.helpdesk"

    # ---- Fields
    request_id = fields.Many2one('res.users',
                                 required=True,
                                 string='Richiedente',
                                 default=lambda self: self.env.user)

    helpdesk_qa_ids = fields.One2many('helpdesk.qa', 'helpdesk_id')

    _track = {
        'state': {
            'enhanced_helpdesk.open': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'open',
            'enhanced_helpdesk.pending': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'pending',
            'enhanced_helpdesk.done': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'done',
            'enhanced_helpdesk.cancel': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'cancel',
        },
    }

    @api.onchange('request_id')
    def onchange_requestid(self):
        self.user_id = False
        if self.request_id:
            self.partner_id = self.request_id.partner_id.parent_id.id
            mail = self.request_id.email
            self.email_from = mail

    @api.model
    def create(self, values):
        res = super(CrmHelpdesk, self).create(values)
        task_value = {
            'partner_id': values['partner_id'],
            'name': values['name'],
            'description': values['description'],
            'ticket_id': res.id,
            }
        self.env['project.task'].sudo().create(task_value)

        # ---- send mail to support for the new ticket
        company = self.env['res.users'].browse(SUPERUSER_ID).company_id
        mail_to = ['"%s" <%s>' % (company.name, company.email_ticket)]
        ir_model_data = self.env['ir.model.data']
        template_id = ir_model_data.get_object_reference(
            'enhanced_helpdesk', 'email_template_ticket_new')[1] or False
        template = self.env['email.template']
        tmpl_br = template.sudo().browse(template_id)
        text = tmpl_br.body_html
        subject = tmpl_br.subject
        text = template.render_template(text, 'crm.helpdesk',
                                        res.id)
        subject = template.render_template(subject, 'crm.helpdesk',
                                           res.id)

        # ---- Get active smtp server
        mail_server = self.env['ir.mail_server'].sudo().search(
            [], limit=1, order='sequence')
        # ---- adding text to reply
        text = '%s\n\n -- %s' % (text, res.description)

        mail_value = {
            'body_html': text,
            'subject': subject,
            'email_from': company.email_ticket,
            'email_to': mail_to,
            'mail_server_id': mail_server.id,
            }
        msg = self.env['mail.mail'].sudo().create(mail_value)
        self.env['mail.mail'].sudo().send([msg.id])
        return res

    @api.multi
    def close_ticket(self):
        self.write({'state': 'done'})

    @api.multi
    def cancel_ticket(self):
        self.write({'state': 'cancel'})

    @api.multi
    def reopen_ticket(self):
        self.write({'state': 'draft'})

    @api.multi
    def working_ticket(self):
        self.write({'state': 'open'})

    @api.multi
    def pending_ticket(self):
        self.write({'state': 'pending'})
