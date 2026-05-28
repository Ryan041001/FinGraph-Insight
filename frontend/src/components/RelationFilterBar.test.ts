import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RelationFilterBar from './RelationFilterBar.vue'

describe('RelationFilterBar', () => {
  it('emits depth changes and relation type toggles', async () => {
    const wrapper = mount(RelationFilterBar, {
      props: {
        depth: 2,
        relationTypes: ['投资', '风险事件'],
        selectedTypes: ['投资']
      }
    })

    await wrapper.find('select').setValue('3')
    await wrapper.findAll('button').find((button) => button.text() === '风险事件')!.trigger('click')

    expect(wrapper.emitted('update:depth')).toEqual([[3]])
    expect(wrapper.emitted('toggle-type')).toEqual([['风险事件']])
    expect(wrapper.findAll('button').find((button) => button.text() === '投资')!.classes()).toContain('active')
  })
})
