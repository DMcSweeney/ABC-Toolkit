<template>
    <div class="w-full p-8">
      <div class="container text-center text-ink-primary text-xl m-auto">
        <h2>Please enter password to access this page.</h2>
        <form v-on:submit.prevent="validateBeforeSubmit" class="flex flex-col items-center gap-3 pt-4">
            <Input class="w-full max-w-xs text-left" label="Password" type="password" v-model.trim="password" />
            <Button type="submit" variant="primary">Submit</Button>
            <div class="text-red-400" v-if="error"><p>Incorrect password.</p></div>
        </form>
      </div>
    </div>
  </template>

  <script>
  import storageHelper from 'storage-helper'
  import router from '@/router';
  import Input from './ui/Input.vue';
  import Button from './ui/Button.vue';
  export default {
    components: { Input, Button },
    data () {
      return {
        error: null,
        password: null,
      }
    },
    methods: {
      validateBeforeSubmit () {
        if (this.password === 'bodycomp') {
          this.error = false
          storageHelper.setItem('user-password', this.password)
          router.push('/')
        } else {
          this.error = true
        }
      }
    }
  }
  </script>